# Jarvis — architecture

A Telegram-triggered Python assistant for queued YouTube transcript capture, Notion storage and AI-assisted weekly teaching preparation.

## Code boundaries

- **src/jarvis/:** Packaged bot, worker, queue and provider adapters.
- **tests/:** Offline queue and authorization tests.
- **pyproject.toml:** Package metadata and installed CLI entry points.
- **requirements.txt:** Dependency snapshot for reproducible setup.
- **.env.example:** Blank integration settings.
- **docs/:** Architecture, configuration and prototype limitations.

## Data boundary

This public repository contains application source and fictional test inputs. Personal/operational state belongs in ignored local storage or separately configured services. Test results establish the behavior exercised by the suite; they do not certify live integrations, product efficacy or deployment readiness.

See the README for implementation status and `CONFIGURATION.md` for provider-specific requirements.
