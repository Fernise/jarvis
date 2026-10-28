import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jarvis.bot import consume_updates, handle_update, is_youtube_url
from jarvis.config import runtime_paths
from jarvis.enqueue_job import enqueue_job
from jarvis.worker import process_next_job


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "JARVIS_DATA_DIR": self.directory.name,
            "TELEGRAM_ALLOWED_CHAT_ID": "demo-chat",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_queued_data_is_private_and_runtime_directories_are_created(self):
        job_id = enqueue_job("demo-chat", "plan", "/plan Demo Learner")
        paths = runtime_paths()
        path = paths["pending"] / f"{job_id}.json"
        job = json.loads(path.read_text())
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["retries"], 0)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertTrue(all(p.is_dir() for p in paths.values()))

    def test_unsupported_text_is_not_queued(self):
        with self.assertRaises(ValueError):
            enqueue_job("demo-chat", "text", "unsupported")
        self.assertEqual(list(runtime_paths()["pending"].iterdir()), [])

    def test_queue_file_becomes_visible_only_after_serialization_finishes(self):
        real_dump = json.dump

        def interleaved_dump(*args, **kwargs):
            self.assertFalse(process_next_job())
            return real_dump(*args, **kwargs)

        with patch("jarvis.enqueue_job.json.dump", side_effect=interleaved_dump):
            job_id = enqueue_job("demo-chat", "plan", "/plan Demo")
        paths = runtime_paths()
        self.assertTrue((paths["pending"] / f"{job_id}.json").exists())
        self.assertEqual(list(paths["failed"].iterdir()), [])

    @patch("jarvis.bot.send_message", side_effect=RuntimeError("synthetic send failure"))
    def test_failed_acknowledgement_does_not_requeue_a_delivered_update(self, send):
        update = {"update_id": 7, "message": {"chat": {"id": "demo-chat"}, "text": "/plan Demo"}}
        with contextlib.redirect_stdout(io.StringIO()):
            offset = consume_updates([update])
            self.assertEqual(consume_updates([update], offset), 8)
        self.assertEqual(len(list(runtime_paths()["pending"].glob("*.json"))), 1)
        send.assert_called_once()

    @patch("jarvis.bot.send_message")
    @patch("jarvis.bot.enqueue_job")
    def test_other_chats_cannot_enqueue_or_receive_messages(self, enqueue, send):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            handle_update({"message": {"chat": {"id": "other"}, "text": "/plan Private"}})
        enqueue.assert_not_called()
        send.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_youtube_matching_checks_host_instead_of_embedded_substrings(self):
        self.assertTrue(is_youtube_url("https://youtu.be/demo"))
        self.assertTrue(is_youtube_url("youtube.com/watch?v=demo"))
        for value in ["https://youtube.com.evil.example/watch?v=demo", "https://example.com/youtu.be/demo", "https://user@youtube.com/watch?v=demo", "https://["]:
            self.assertFalse(is_youtube_url(value))

    @patch("jarvis.worker.send_message")
    @patch("jarvis.worker.process", side_effect=RuntimeError("synthetic confidential response"))
    def test_failures_retry_twice_then_stop_without_recording_provider_details(self, process, send):
        job_id = enqueue_job("demo-chat", "plan", "/plan Demo")
        for _ in range(3):
            self.assertTrue(process_next_job())
        paths = runtime_paths()
        failed = paths["failed"] / f"{job_id}.json"
        job = json.loads(failed.read_text())
        self.assertEqual(job["retries"], 3)
        self.assertEqual(job["status"], "failed")
        self.assertNotIn("confidential", failed.read_text())
        self.assertEqual(list(paths["pending"].iterdir()), [])
        self.assertEqual(process.call_count, 3)
        send.assert_called_once()

    @patch("jarvis.worker.send_message", side_effect=RuntimeError("notification failed"))
    @patch("jarvis.worker.process", return_value=subprocess.CompletedProcess([], 0, "Demo plan", ""))
    def test_notification_failure_does_not_repeat_completed_external_work(self, process, send):
        job_id = enqueue_job("demo-chat", "plan", "/plan Demo")
        process_next_job()
        paths = runtime_paths()
        job = json.loads((paths["done"] / f"{job_id}.json").read_text())
        self.assertEqual(job["status"], "done")
        self.assertFalse(job["notification_delivered"])
        self.assertFalse(process_next_job())
        process.assert_called_once()

    @patch("jarvis.worker.process")
    def test_worker_rejects_a_job_for_another_chat(self, process):
        job_id = enqueue_job("another-chat", "plan", "/plan Demo")
        process_next_job()
        self.assertTrue((runtime_paths()["failed"] / f"{job_id}.json").exists())
        process.assert_not_called()

    @patch("jarvis.worker.process")
    def test_malformed_queue_record_does_not_call_external_services(self, process):
        path = runtime_paths()["pending"] / "broken.json"
        path.write_text("not json")
        process_next_job()
        self.assertTrue((runtime_paths()["failed"] / path.name).exists())
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
