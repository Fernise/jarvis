import os
import requests
from .config import load_environment, require


def headers():
    load_environment()
    return {
        "Authorization": "Bearer " + require("NOTION_TOKEN"),
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def query_database(database_id):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    res = requests.post(url, headers=headers(), json={}, timeout=30)
    res.raise_for_status()
    return res.json()["results"]

def get_speaking(database_id):
    pages = query_database(database_id)

    results = []

    for page in pages:
        props = page["properties"]

        theme = props["Theme"]["title"][0]["plain_text"] if props["Theme"]["title"] else ""
        level = props["Level"]["select"]["name"] if props["Level"]["select"] else ""
        status = props["Status"]["select"]["name"] if props["Status"]["select"] else ""

        topic_rel = props["Topic"]["relation"]
        topic_id = topic_rel[0]["id"] if topic_rel else ""

        # 👇 AQUÍ ES DONDE VA
        students_rel = props.get("Students", {}).get("relation", [])
        student_ids = [s["id"] for s in students_rel]

        results.append({
            "theme": theme,
            "level": level,
            "status": status,
            "topic_id": topic_id,
            "student_ids_done": student_ids  # 👈 nuevo campo
        })

    return results

def get_students_map(database_id):
    pages = query_database(database_id)
    mapping = {}

    for page in pages:
        props = page["properties"]
        name = props["Name"]["title"][0]["plain_text"] if props["Name"]["title"] else ""
        mapping[page["id"]] = name

    return mapping


def get_topics_map(database_id):
    pages = query_database(database_id)

    mapping = {}

    for page in pages:
        props = page["properties"]
        name = props["Topic"]["title"][0]["plain_text"]
        mapping[page["id"]] = name

    return mapping

def get_students(database_id):
    pages = query_database(database_id)
    students = []

    for page in pages:
        props = page["properties"]

        name = props["Name"]["title"][0]["plain_text"] if props["Name"]["title"] else ""

        level = (
            props["English Level"]["select"]["name"]
            if props["English Level"]["select"]
            else ""
        )

        profile_text = get_page_text(page["id"])

        students.append({
            "name": name,
            "level": level,
            "profile_text": profile_text
        })

    return students

def get_page_text(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    res = requests.get(url, headers=headers(), timeout=30)
    res.raise_for_status()

    blocks = res.json()["results"]
    texts = []

    for block in blocks:
        block_type = block["type"]
        data = block.get(block_type, {})

        rich_text = data.get("rich_text", [])
        for t in rich_text:
            texts.append(t.get("plain_text", ""))

    return "\n".join(texts).strip()