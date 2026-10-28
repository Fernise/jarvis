"""Save a transcript from stdin; do not place content in process arguments."""
import argparse
import sys
from datetime import datetime
from notion_client import Client
from .config import load_environment, require


def paragraph_blocks(text, chunk_size=1900):
    return [
        {"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[i:i + chunk_size]}}]
        }}
        for i in range(0, len(text), chunk_size)
    ]


def main():
    load_environment()
    parser = argparse.ArgumentParser(description="Save a transcript from stdin to Notion.")
    parser.add_argument("--url", default="")
    args = parser.parse_args()
    raw = sys.stdin.read().strip()
    if not raw:
        parser.error("A transcript is required on stdin")
    title, text = raw.split("###TRANSCRIPT###", 1) if "###TRANSCRIPT###" in raw else ("YouTube Transcript", raw)
    try:
        notion = Client(auth=require("NOTION_TOKEN"), notion_version="2022-06-28")
        database_id = require("NOTION_DATABASE_ID")
        schema = notion.databases.retrieve(database_id=database_id).get("properties", {})
        title_property = next((name for name, prop in schema.items() if prop.get("type") == "title"), None)
        if not title_property:
            raise ValueError("Missing title property")
        properties = {title_property: {"title": [{"text": {"content": f"{title.strip()} - {datetime.now():%Y-%m-%d}"[:100]}}]}}
        if args.url:
            url_property = next((name for name, prop in schema.items() if prop.get("type") == "url"), None)
            if url_property:
                properties[url_property] = {"url": args.url}
        blocks = paragraph_blocks(" ".join(text.split()))
        page = notion.pages.create(parent={"database_id": database_id}, properties=properties, children=blocks[:100])
        for offset in range(100, len(blocks), 100):
            notion.blocks.children.append(block_id=page["id"], children=blocks[offset:offset + 100])
    except Exception:
        print("Notion save failed. Check schema, permissions and configuration.", file=sys.stderr)
        return 1
    print("Transcript saved to Notion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
