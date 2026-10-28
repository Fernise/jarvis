#!/usr/bin/env python3
import argparse
import json
import os
import re
from openai import OpenAI
from .notion_reader import get_speaking, get_students_map, get_topics_map, get_students
from .config import load_environment

load_environment()


SYSTEM_PROMPT = """
You are a weekly preparation assistant for English lessons.

Your task is ONLY to select speaking themes from the provided Notion data.

The output is for the teacher only.
The goal is to help the teacher decide which speaking materials to prepare.

Rules:
- Select ONLY speaking themes from the provided list.
- Do NOT invent topics.
- Do NOT create exercises.
- Do NOT generate vocabulary.
- Do NOT suggest what to upload.
- The teacher will use the linked vocabulary in Notion manually.
- Do NOT select a speaking theme for a student if that student is listed in students_done.
- If a theme is done by some students but not others, assign it only to the students who have not done it.
- Only assign a theme to students listed in eligible_students for that theme.
- Never assign a theme to a student who is not in eligible_students.

Student handling:
- The user will provide a list of student names.
- Plan ONLY for the requested students.
- Use the student's plain-text profile, objectives, interests and notes when choosing themes.

Academic students:
- If a student has "STUDENT TYPE: Academic", EXCLUDE them from planning.
- If ALL requested students are Academic, return:
  {
    "title": "Weekly Preparation Checklist",
    "items": [],
    "message": "No weekly planning needed (academic students)."
  }

Theme selection:
- Prefer themes not already covered (status: Not introduced).
- If already covered, mark as "Review" or "Related".
- Select at most 2 items unless explicitly requested otherwise.

Grouping logic (VERY IMPORTANT):
- Your priority is to minimize the number of different speaking themes the teacher has to prepare.
- Prefer themes that can work for multiple students.
- Group students under the same theme whenever it is reasonably suitable.
- Do NOT force grouping if the theme clearly does not fit a student.
- If one shared theme works for all students → return ONE item.
- Otherwise → return the smallest number of groups possible.

Output:
- Return valid JSON only.

Required JSON format:
{
  "title": "Weekly Preparation Checklist",
  "items": [
    {
      "students": ["Student name"],
      "speaking_theme": "Theme exactly as provided",
      "broad_topic": "Topic exactly as provided",
      "status": "New | Review | Related",
      "reason": "Short practical reason"
    }
  ]
}
"""

def generate_planning(user_input, students, topics):
    payload = {
        "user_request": user_input,
        "available_speaking_topics": topics,
        "students": students
    }

    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        temperature=0.2
    )

    return json.loads(response.output_text)

def format_preparation_output(planning):
    lines = []
    lines.append("WEEKLY PREPARATION CHECKLIST\n")

    if not planning["items"]:
        return "No planning items."

    for item in planning["items"]:
        students = ", ".join(item["students"])

        lines.append(f"{students}")
        lines.append(f"- Speaking: {item['speaking_theme']}")
        lines.append(f"  Topic: {item['broad_topic']}")
        lines.append(f"  Status: {item['status']}")
        lines.append(f"  Reason: {item['reason']}")
        lines.append("")

    return "\n".join(lines)

def save_planning(planning):
    # TODO: replace with Notion save
    print(json.dumps(planning, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input")
    group.add_argument("--stdin", action="store_true")
    args = parser.parse_args()
    if args.stdin:
        import sys
        args.input = sys.stdin.read()

    SPEAKING_DB = os.getenv("NOTION_SPEAKING_DB")
    TOPICS_DB = os.getenv("NOTION_TOPICS_DB")
    STUDENTS_DB = os.getenv("NOTION_STUDENTS_DB")

    students = get_students(STUDENTS_DB)
    speaking = get_speaking(SPEAKING_DB)
    topics_map = get_topics_map(TOPICS_DB)
    students_map = get_students_map(STUDENTS_DB)

    user_input = args.input.lower()
    selected_students = [
        student for student in students
        if re.search(r"(?<!\w)" + re.escape(student["name"].casefold()) + r"(?!\w)", user_input.casefold())
    ]
    if not selected_students:
        raise SystemExit("No requested students matched the configured catalog")
    requested_students = [student["name"] for student in selected_students]


    catalog = []

    for item in speaking:
        students_done = [
            students_map.get(student_id, student_id)
            for student_id in item.get("student_ids_done", [])
        ]

        eligible_students = [
            name for name in requested_students
            if name not in students_done
        ]

        if not eligible_students:
            continue

        catalog.append({
            "theme": item["theme"],
            "topic": topics_map.get(item["topic_id"], ""),
            "level": item["level"],
            "status": item["status"],
            "students_done": students_done,
            "eligible_students": eligible_students
        })

    planning = generate_planning(args.input, selected_students, catalog)

    formatted = format_preparation_output(planning)
    print(formatted)

if __name__ == "__main__":
    main()