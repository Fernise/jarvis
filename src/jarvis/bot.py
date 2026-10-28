"""Single-chat Telegram entry point. Message bodies are never logged."""
import json
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from .config import load_environment, require
from .enqueue_job import enqueue_job


def tg_api(method, data=None):
    token = require("TELEGRAM_BOT_TOKEN")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(data or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def send_message(chat_id, text):
    tg_api("sendMessage", {"chat_id": chat_id, "text": text[:4000]})


def is_youtube_url(text):
    candidate = text.strip()
    if not candidate.startswith(("https://", "http://")):
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
            and parsed.username is None
            and bool(parsed.path.strip("/"))
        )
    except ValueError:
        return False


def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = str(message.get("chat", {}).get("id", ""))
    if chat_id != require("TELEGRAM_ALLOWED_CHAT_ID"):
        return
    text = (message.get("text") or "").strip()
    if text in {"/start", "/help"} or not text:
        send_message(chat_id, "Jarvis: send a YouTube URL or /plan followed by student names.")
        return
    if is_youtube_url(text):
        kind = "youtube"
    elif text.lower().startswith(("planning ", "plan ", "/planning ", "/plan ")):
        kind = "plan"
    else:
        send_message(chat_id, "Supported tasks: a YouTube URL or /plan followed by student names.")
        return
    try:
        job_id = enqueue_job(chat_id, kind, text)
    except Exception:
        send_message(chat_id, "Unable to queue this task. Check the local worker.")
        return
    send_message(chat_id, f"Task queued. Type: {kind}. Job ID: {job_id}")


def consume_updates(updates, offset=None):
    for update in updates:
        update_id = update.get("update_id") if isinstance(update, dict) else None
        if type(update_id) is not int or (offset is not None and update_id < offset):
            continue
        # An acknowledgement failure must not enqueue the same update again.
        offset = update_id + 1
        try:
            handle_update(update)
        except Exception:
            print("Update handling failed; private request details omitted.")
    return offset


def main():
    load_environment()
    require("TELEGRAM_BOT_TOKEN")
    require("TELEGRAM_ALLOWED_CHAT_ID")
    offset = None
    print("Jarvis bot started.")
    while True:
        try:
            payload = {"timeout": 30, "allowed_updates": ["message", "edited_message"]}
            if offset is not None:
                payload["offset"] = offset
            response = tg_api("getUpdates", payload)
            if not response.get("ok"):
                time.sleep(3)
                continue
            offset = consume_updates(response.get("result", []), offset)
        except KeyboardInterrupt:
            return
        except Exception:
            # Exception text can contain the token-bearing request URL.
            print("Telegram request failed; retrying. No request details logged.")
            time.sleep(5)


if __name__ == "__main__":
    main()
