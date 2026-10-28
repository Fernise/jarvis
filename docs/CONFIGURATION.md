# Configuration

## Credentials

Copy `.env.example` to ignored `.env` in the working directory. Both commands load that file; `JARVIS_ENV_FILE` can explicitly select another private environment file.

| Variable | Used by |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot polling and worker completion messages |
| `TELEGRAM_ALLOWED_CHAT_ID` | Single permitted chat; missing configuration fails closed |
| `SUPADATA_API_KEY` | Transcript retrieval |
| `NOTION_TOKEN` | Read authorized teaching data and save transcripts |
| `NOTION_DATABASE_ID` | Transcript destination database |
| `NOTION_SPEAKING_DB` | Speaking-theme catalog |
| `NOTION_TOPICS_DB` | Topic catalog |
| `NOTION_STUDENTS_DB` | Teacher-controlled student profiles |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Weekly preparation selection |
| `JARVIS_DATA_DIR` | Private runtime directory; default `data/` |

Use provider credentials with the least access required. No credentials, database IDs, profiles or chat history are included.

## Notion schema expected by this prototype

The reader preserves the original database API/schema assumptions and needs an integration shared with the selected databases:

- Students: a `Name` title, `English Level` select and profile text in page blocks.
- Topics: a `Topic` title.
- Speaking catalog: `Theme` title, `Level`/`Status` selects, `Topic` relation and `Students` relation for already-completed themes.
- Transcript destination: one title property and an optional URL property, discovered from the schema.

Notion account/API-version compatibility must be checked in an isolated integration rehearsal; offline tests do not validate provider access. The transcript saver reads its content from stdin rather than command-line arguments.

## Queue operations

Run a single worker for each runtime directory. Queue files are created mode `0600`; directories are mode `0700` on POSIX systems. Personal inputs remain in those local files until the operator deletes them.

A failed task is retried twice. A notification failure after task completion does not rerun the task. Jobs left under `processing/` after an interrupted process need manual inspection; do not blindly replay them because an external write may already have happened. Exactly-once external delivery and multi-worker coordination are not implemented.

Application logs omit message bodies, provider response details and credentials. Completed planning output is deliberately sent only to the configured authorized chat.
