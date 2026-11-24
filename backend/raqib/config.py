"""Runtime configuration, read from the environment (and an optional .env file)."""

from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
ROOT_DIR = PKG_DIR.parent.parent
DATA_DIR = PKG_DIR / "data"
CASES_DIR = DATA_DIR / "cases"
FEEDS_DIR = DATA_DIR / "feeds"
RUNS_DIR = DATA_DIR / "runs"
EVIDENCE_DIR = DATA_DIR / "evidence"
LIVE_CASES_DIR = DATA_DIR / "live_cases"  # real scans kept for campaign linking (git-ignored)
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def _load_dotenv() -> None:
    """Tiny .env loader so we do not need another dependency."""
    env_file = ROOT_DIR / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def model_label() -> str:
    """Human name of the configured model, e.g. 'Claude Sonnet 5.5'."""
    m = model_name().removeprefix("claude-").split("-")
    family = m[0].capitalize() if m else "Claude"
    version = ".".join(x for x in m[1:] if x.isdigit())
    return f"Claude {family} {version}".strip()


def model_name() -> str:
    return os.environ.get("RAQIB_MODEL", "claude-sonnet-5-5").strip() or "claude-sonnet-5-5"


def requested_mode() -> str:
    return os.environ.get("RAQIB_MODE", "auto").strip().lower()


def set_api_key(key: str) -> None:
    """Set the key for this process and persist it to the local, git-ignored .env."""
    key = key.strip()
    os.environ["ANTHROPIC_API_KEY"] = key
    env_file = ROOT_DIR / ".env"
    lines: list[str] = []
    if env_file.is_file():
        lines = [ln for ln in env_file.read_text(encoding="utf-8").splitlines() if not ln.startswith("ANTHROPIC_API_KEY=")]
    lines.append(f"ANTHROPIC_API_KEY={key}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
