"""Read Nanobot sessions from local JSONL transcripts."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .. import paths
from .base import SessionEvent, TokenUsage
from .utils import collect_jsonl_files, iter_jsonl

PROVIDER = "nanobot"


def default_root() -> Path:
    return paths.nanobot_sessions_dir()


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    yield from collect_jsonl_files(root or default_root())


def iter_events(root: Path | None = None) -> Iterator[SessionEvent]:
    for path in iter_session_files(root):
        yield from _iter_file_events(path)


def iter_token_usage(root: Path | None = None) -> Iterator[TokenUsage]:
    for path in iter_session_files(root):
        yield from _iter_file_token_usage(path)


def _iter_file_events(path: Path) -> Iterator[SessionEvent]:
    session_id = path.stem
    created_at: str | None = None

    for entry in iter_jsonl(path):
        if entry.get("_type") == "metadata":
            created_at = _as_str(entry.get("created_at")) or created_at
            continue

        role = _as_str(entry.get("role"))
        if not role:
            continue

        timestamp = _as_str(entry.get("timestamp")) or created_at
        content = _as_str(entry.get("content"))
        if content:
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="message",
                timestamp=timestamp,
                text=content,
            )

        yield from _iter_tool_events(path, session_id, role, timestamp, entry)


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session_id = path.stem

    for entry in iter_jsonl(path):
        if entry.get("_type") == "metadata":
            continue
        usage = _dict_or_empty(entry.get("usage"))
        if not usage:
            continue

        cost = _dict_or_empty(usage.get("cost"))
        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=_as_str(entry.get("timestamp")),
            model=_as_str(entry.get("model")),
            input_tokens=_as_int(usage.get("input")),
            output_tokens=_as_int(usage.get("output")),
            reasoning_tokens=_as_int(usage.get("reasoning")),
            cache_read_tokens=_as_int(usage.get("cacheRead")),
            cache_write_tokens=_as_int(usage.get("cacheWrite")),
            total_tokens=_optional_int(usage.get("totalTokens")),
            cost=_as_float(cost.get("total")),
        )


def _iter_tool_events(
    path: Path,
    session_id: str,
    role: str,
    timestamp: str | None,
    entry: dict[str, Any],
) -> Iterator[SessionEvent]:
    tools_used = entry.get("tools_used")
    if isinstance(tools_used, list):
        for tool in tools_used:
            name = _as_str(tool)
            if name:
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=session_id,
                    source_path=path,
                    role=role,
                    kind="tool_use",
                    timestamp=timestamp,
                    name=name,
                )

    tool_calls = entry.get("tool_calls") or entry.get("toolCalls")
    if not isinstance(tool_calls, list):
        return

    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        yield SessionEvent(
            provider=PROVIDER,
            session_id=session_id,
            source_path=path,
            role=role,
            kind="tool_use",
            timestamp=timestamp,
            name=_as_str(call.get("name")) or _as_str(call.get("tool")),
            input=_dict_or_empty(call.get("arguments") or call.get("args")),
        )


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
