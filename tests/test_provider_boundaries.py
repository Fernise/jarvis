import contextlib
import io
import os
import unittest
from unittest.mock import MagicMock, patch

from jarvis.save_to_notion import main as save_to_notion
from jarvis.youtube_transcript_api import main as transcript
from jarvis import weekly_planner


class ProviderBoundaryTests(unittest.TestCase):
    def test_only_explicitly_requested_student_profiles_are_sent_to_generation(self):
        selected = {"name": "Demo Learner", "level": "B1", "profile_text": "Fictional selected profile"}
        other = {"name": "Other Learner", "level": "B2", "profile_text": "Unrequested private profile"}
        with patch.object(weekly_planner, "get_students", return_value=[selected, other]), patch.object(weekly_planner, "get_speaking", return_value=[]), patch.object(weekly_planner, "get_topics_map", return_value={}), patch.object(weekly_planner, "get_students_map", return_value={}), patch.object(weekly_planner, "generate_planning", return_value={"items": []}) as generate, patch("sys.argv", ["jarvis-plan", "--input", "/plan Demo Learner"]), contextlib.redirect_stdout(io.StringIO()):
            weekly_planner.main()
        self.assertEqual(generate.call_args.args[1], [selected])
        self.assertNotIn("Other Learner", str(generate.call_args))

    @patch("jarvis.youtube_transcript_api.requests.get")
    def test_missing_or_malformed_transcript_is_not_treated_as_content(self, get):
        for content in [None, 123, {}, [{"text": None}]]:
            get.return_value.json.return_value = {"content": content}
            output = io.StringIO()
            with patch.dict(os.environ, {"SUPADATA_API_KEY": "synthetic-value"}), patch("sys.argv", ["transcript", "https://youtu.be/demo"]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(transcript(), 1)
            self.assertEqual(output.getvalue(), "")

    @patch("jarvis.save_to_notion.Client")
    def test_notion_schema_and_writer_use_the_same_explicit_api_version(self, client):
        client.return_value.databases.retrieve.return_value = {"properties": {"Title": {"type": "title"}}}
        client.return_value.pages.create.return_value = {"id": "demo-page"}
        with patch.dict(os.environ, {"NOTION_TOKEN": "synthetic-value", "NOTION_DATABASE_ID": "demo-database"}), patch("sys.argv", ["save"]), patch("sys.stdin", io.StringIO("Demo###TRANSCRIPT###Fictional transcript")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(save_to_notion(), 0)
        client.assert_called_once_with(auth="synthetic-value", notion_version="2022-06-28")
