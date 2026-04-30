"""Read OpenCode sessions from the local SQLite database."""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import paths
from .base import SessionEvent, TokenUsage

PROVIDER = "opencode"


def default_root() -> Path:
    return paths.opencode_data_dir()


def iter_database_files(root: Path | None = None) -> Iterator[Path]:
    base = root or default_root()
    if base.is_file():
        yield base
        return
    if not base.is_dir():
        return

    for path in sorted(base.glob("opencode*.db")):
        if path.name.endswith(("-shm", "-wal")):
            continue
        yield path


def iter_events(root: Path | None = None) -> Iterator[SessionEvent]:
    for path in iter_database_files(root):
        yield from _iter_database_events(path)


def iter_token_usage(root: Path | None = None) -> Iterator[TokenUsage]:
    for path in iter_database_files(root):
        yield from _iter_database_token_usage(path)


def _iter_database_events(path: Path) -> Iterator[SessionEvent]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return

    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        rows = conn.execute(
            """
            SELECT
              s.id AS session_id,
              s.directory AS session_directory,
              p.worktree AS project_worktree,
              m.id AS message_id,
              m.time_created AS message_created,
              m.data AS message_data,
              part.time_created AS part_created,
              part.time_updated AS part_updated,
              part.data AS part_data
            FROM part
            JOIN message m ON m.id = part.message_id
            JOIN session s ON s.id = m.session_id
            LEFT JOIN project p ON p.id = s.project_id
            ORDER BY s.id, m.time_created, m.id, part.time_created, part.id
            """
        )

        for row in rows:
            message_data = _json_dict(row["message_data"])
            part_data = _json_dict(row["part_data"])
            role = _as_str(message_data.get("role")) or "unknown"
            project_dir = _project_dir(message_data, row["project_worktree"], row["session_directory"])

            part_type = part_data.get("type")
            if part_type == "text":
                text = _as_str(part_data.get("text"))
                if not text:
                    continue
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=row["session_id"],
                    source_path=path,
                    role=role,
                    kind="message",
                    timestamp=_timestamp(row["message_created"]),
                    project_dir=project_dir,
                    text=text,
                )
            elif part_type == "tool":
                state = _dict_or_empty(part_data.get("state"))
                state_time = _dict_or_empty(state.get("time"))
                tool_input = _dict_or_empty(state.get("input"))
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=row["session_id"],
                    source_path=path,
                    role=role,
                    kind="tool_use",
                    timestamp=_timestamp(state_time.get("start") or row["part_created"]),
                    project_dir=project_dir,
                    name=_as_str(part_data.get("tool")),
                    input=tool_input,
                )

                result_text = _tool_result_text(state)
                if result_text:
                    yield SessionEvent(
                        provider=PROVIDER,
                        session_id=row["session_id"],
                        source_path=path,
                        role="tool",
                        kind="tool_result",
                        timestamp=_timestamp(state_time.get("end") or row["part_updated"]),
                        project_dir=project_dir,
                        name=_as_str(part_data.get("tool")),
                        text=result_text,
                    )
    except sqlite3.Error:
        return
    finally:
        conn.close()


def _iter_database_token_usage(path: Path) -> Iterator[TokenUsage]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return

    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        rows = conn.execute(
            """
            SELECT
              s.id AS session_id,
              s.directory AS session_directory,
              p.worktree AS project_worktree,
              m.time_created AS message_created,
              m.data AS message_data
            FROM message m
            JOIN session s ON s.id = m.session_id
            LEFT JOIN project p ON p.id = s.project_id
            ORDER BY s.id, m.time_created, m.id
            """
        )

        for row in rows:
            message_data = _json_dict(row["message_data"])
            tokens = _dict_or_empty(message_data.get("tokens"))
            if not tokens:
                continue

            cache = _dict_or_empty(tokens.get("cache"))
            yield TokenUsage(
                provider=PROVIDER,
                source_path=path,
                session_id=row["session_id"],
                timestamp=_timestamp(row["message_created"]),
                project_dir=_project_dir(message_data, row["project_worktree"], row["session_directory"]),
                model=_as_str(message_data.get("modelID")),
                input_tokens=_as_int(tokens.get("input")),
                output_tokens=_as_int(tokens.get("output")),
                reasoning_tokens=_as_int(tokens.get("reasoning")),
                cache_read_tokens=_as_int(cache.get("read")),
                cache_write_tokens=_as_int(cache.get("write")),
                cost=_as_float(message_data.get("cost")),
            )
    except sqlite3.Error:
        return
    finally:
        conn.close()


def _project_dir(message_data: dict[str, Any], worktree: object, directory: object) -> str | None:
    path_info = message_data.get("path")
    if isinstance(path_info, dict):
        return _as_str(path_info.get("cwd")) or _as_str(path_info.get("root"))
    return _as_str(worktree) or _as_str(directory)


def _tool_result_text(state: dict[str, Any]) -> str | None:
    status = state.get("status")
    if status == "completed":
        return _as_str(state.get("output"))
    if status == "error":
        return _as_str(state.get("error"))
    return None


def _json_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _timestamp(value: object) -> str | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, UTC).isoformat().replace("+00:00", "Z")
    return _as_str(value)


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and value >= 0 else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
