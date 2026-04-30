"""Read pi-agent sessions from local JSONL transcripts."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import paths
from .base import SessionEvent, TokenUsage
from .utils import collect_jsonl_files, extract_text, iter_jsonl

PROVIDER = "pi"


def default_root() -> Path:
    return paths.pi_sessions_dir()


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    yield from collect_jsonl_files(root or default_root())


def iter_events(root: Path | None = None) -> Iterator[SessionEvent]:
    for path in iter_session_files(root):
        yield from _iter_file_events(path)


def iter_token_usage(root: Path | None = None) -> Iterator[TokenUsage]:
    for path in iter_session_files(root):
        yield from _iter_file_token_usage(path)


def _iter_file_events(path: Path) -> Iterator[SessionEvent]:
    session_id: str | None = None
    project_dir: str | None = None

    for entry in iter_jsonl(path):
        entry_type = entry.get("type")
        timestamp = _timestamp(entry.get("timestamp"))

        if entry_type == "session":
            session_id = _as_str(entry.get("id")) or session_id
            project_dir = _as_str(entry.get("cwd")) or project_dir
            continue

        if entry_type != "message":
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        role = _as_str(message.get("role")) or "unknown"
        timestamp = timestamp or _timestamp(message.get("timestamp"))

        if role == "toolResult":
            text = extract_text(message.get("content")).strip()
            if text:
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=session_id,
                    source_path=path,
                    role="tool",
                    kind="tool_result",
                    timestamp=timestamp,
                    project_dir=project_dir,
                    name=_as_str(message.get("toolName")),
                    text=text,
                )
            continue

        text = extract_text(message.get("content")).strip()
        if text:
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="message",
                timestamp=timestamp,
                project_dir=project_dir,
                text=text,
            )

        content = message.get("content")
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                continue
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="tool_use",
                timestamp=timestamp,
                project_dir=project_dir,
                name=_as_str(block.get("name")),
                input=_dict_or_empty(block.get("arguments")),
            )


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session_id: str | None = None
    project_dir: str | None = None

    for entry in iter_jsonl(path):
        entry_type = entry.get("type")
        timestamp = _timestamp(entry.get("timestamp"))

        if entry_type == "session":
            session_id = _as_str(entry.get("id")) or session_id
            project_dir = _as_str(entry.get("cwd")) or project_dir
            continue

        if entry_type != "message":
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue

        cost = _dict_or_empty(usage.get("cost"))
        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=timestamp or _timestamp(message.get("timestamp")),
            project_dir=project_dir,
            model=_as_str(message.get("model")),
            input_tokens=_as_int(usage.get("input")),
            output_tokens=_as_int(usage.get("output")),
            cache_read_tokens=_as_int(usage.get("cacheRead")),
            cache_write_tokens=_as_int(usage.get("cacheWrite")),
            total_tokens=_optional_int(usage.get("totalTokens")),
            cost=_as_float(cost.get("total")),
        )


def _timestamp(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, UTC).isoformat().replace("+00:00", "Z")
    return None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and value >= 0 else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
