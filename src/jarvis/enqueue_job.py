import json
import os
import uuid
from datetime import datetime, timezone
from .config import runtime_paths


def enqueue_job(chat_id: str, kind: str, text: str) -> str:
    if kind not in {"youtube", "plan"}:
        raise ValueError("Unsupported job type")
    if not text.strip():
        raise ValueError("A job needs input")
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id, "chat_id": str(chat_id), "kind": kind,
        "input": text, "status": "queued", "retries": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    directory = runtime_paths()["pending"]
    path = directory / f"{job_id}.json"
    temporary = directory / f".{job_id}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(job, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return job_id
