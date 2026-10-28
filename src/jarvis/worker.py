"""Single-process local queue with bounded retries; never log task payloads."""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from .bot import send_message
from .config import load_environment, require, runtime_paths

MAX_RETRIES = 2


def save_job(path, job):
    with path.open("w", encoding="utf-8") as file:
        json.dump(job, file, ensure_ascii=False, indent=2)
    path.chmod(0o600)


def process(job):
    common = {"capture_output": True, "text": True, "timeout": 180}
    if job["kind"] == "plan":
        return subprocess.run(
            [sys.executable, "-m", "jarvis.weekly_planner", "--stdin"],
            input=job["input"], **common,
        )
    if job["kind"] == "youtube":
        transcript = subprocess.run(
            [sys.executable, "-m", "jarvis.youtube_transcript_api", job["input"]], **common,
        )
        if transcript.returncode or not transcript.stdout.strip():
            raise RuntimeError("transcript_unavailable")
        return subprocess.run(
            [sys.executable, "-m", "jarvis.save_to_notion", "--url", job["input"]],
            input=transcript.stdout, **common,
        )
    raise ValueError("Unsupported job type")


def notify(job, text):
    try:
        send_message(job["chat_id"], text)
    except Exception:
        # A notification failure must not repeat an already completed external job.
        return False
    return True


def process_next_job():
    paths = runtime_paths()
    pending = sorted(paths["pending"].glob("*.json"))
    if not pending:
        return False
    path = paths["processing"] / pending[0].name
    pending[0].rename(path)
    try:
        job = json.loads(path.read_text())
        if job.get("job_id") != path.stem or str(job["chat_id"]) != require("TELEGRAM_ALLOWED_CHAT_ID"):
            raise ValueError("Invalid job identity")
        job["status"] = "running"
        job["started_at"] = datetime.now(timezone.utc).isoformat()
        save_job(path, job)
    except (ValueError, KeyError):
        path.rename(paths["failed"] / path.name)
        return True
    try:
        result = process(job)
        if result.returncode:
            raise RuntimeError("task_failed")
    except Exception:
        job["retries"] = job.get("retries", 0) + 1
        job["last_error"] = "task_failed"
        job["status"] = "queued" if job["retries"] <= MAX_RETRIES else "failed"
        save_job(path, job)
        path.rename(paths["pending" if job["status"] == "queued" else "failed"] / path.name)
        if job["status"] == "failed":
            notify(job, f"Task failed after retries. Job ID: {job['job_id']}")
    else:
        job["status"] = "done"
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_job(path, job)
        path.rename(paths["done"] / path.name)
        text = result.stdout if job["kind"] == "plan" else "Transcript saved to Notion."
        job["notification_delivered"] = notify(job, text or "Task completed.")
        save_job(paths["done"] / path.name, job)
    return True


def main():
    load_environment()
    require("TELEGRAM_BOT_TOKEN")
    require("TELEGRAM_ALLOWED_CHAT_ID")
    print("Jarvis worker started. Run only one worker for this queue.")
    while True:
        try:
            process_next_job()
            time.sleep(2)
        except KeyboardInterrupt:
            return
        except Exception:
            print("Queue operation failed. Inspect private queue state before restarting.")
            time.sleep(5)


if __name__ == "__main__":
    main()
