"""Default filesystem roots for local agent data."""

import os
from pathlib import Path


def home_dir() -> Path:
    override = os.environ.get("AGENTYPE_TEST_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    try:
        return Path.home()
    except RuntimeError:
        return Path(".")


def agents_skills_dir() -> Path:
    return home_dir() / ".agents" / "skills"


def claude_dir() -> Path:
    return home_dir() / ".claude"


def claude_projects_dir() -> Path:
    return claude_dir() / "projects"


def claude_skills_dir() -> Path:
    return claude_dir() / "skills"


def codex_dir() -> Path:
    return home_dir() / ".codex"


def codex_skills_dir() -> Path:
    return codex_dir() / "skills"


def opencode_data_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if data_home:
        return Path(data_home).expanduser() / "opencode"
    return home_dir() / ".local" / "share" / "opencode"


def pi_sessions_dir() -> Path:
    return home_dir() / ".pi" / "agent" / "sessions"


def gemini_dir() -> Path:
    return home_dir() / ".gemini"


def openclaw_agents_dir() -> Path:
    return home_dir() / ".openclaw" / "agents"


def nanobot_sessions_dir() -> Path:
    return home_dir() / ".nanobot" / "sessions"
