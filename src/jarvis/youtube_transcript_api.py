import argparse
import sys
import requests
from .bot import is_youtube_url
from .config import load_environment, require


def main():
    load_environment()
    parser = argparse.ArgumentParser(description="Fetch a transcript through Supadata.")
    parser.add_argument("url")
    args = parser.parse_args()
    if not is_youtube_url(args.url):
        parser.error("Provide a YouTube URL")
    try:
        response = requests.get(
            "https://api.supadata.ai/v1/transcript",
            headers={"x-api-key": require("SUPADATA_API_KEY"), "User-Agent": "jarvis-bot/0.1"},
            params={"url": args.url}, timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        if isinstance(content, str):
            text = content
        elif isinstance(content, list) and all(
            isinstance(item, dict) and isinstance(item.get("text"), str) for item in content
        ):
            text = " ".join(item["text"] for item in content)
        else:
            raise ValueError("Invalid transcript content")
        if not text.strip():
            raise ValueError("No transcript")
    except Exception:
        print("Transcript unavailable. Check provider configuration and quota.", file=sys.stderr)
        return 1
    print(data.get("title", "YouTube Video"))
    print("###TRANSCRIPT###")
    print(text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
