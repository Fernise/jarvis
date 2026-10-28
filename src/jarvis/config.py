"""Local configuration and private runtime paths; no embedded credentials."""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment():
    load_dotenv(Path(os.environ.get("JARVIS_ENV_FILE", ".env")), override=False)


def require(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Configure {name} in your local environment")
    return value


def runtime_paths():
    root = Path(os.environ.get("JARVIS_DATA_DIR", "data")).expanduser().resolve()
    paths = {name: root / "jobs" / name for name in ("pending", "processing", "done", "failed")}
    paths["logs"] = root / "logs"
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    return paths
