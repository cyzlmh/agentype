"""Read Gemini CLI sessions from local JSON transcripts."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .. import paths
from .base import SessionEvent, TokenUsage
from .utils import extract_text

PROVIDER = "gemini"


def default_root() -> Path:
    return paths.gemini_dir()


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    base = root or default_root()
    tmp_dir = base / "tmp" if base.name != "tmp" else base
    if not tmp_dir.is_dir():
        return

    for path in sorted(tmp_dir.glob("*/chats/session-*.json")):
        if path.is_file():
            yield path


def iter_events(root: Path | None = None) -> Iterator[SessionEvent]:
    for path in iter_session_files(root):
        yield from _iter_file_events(path)


def iter_token_usage(root: Path | None = None) -> Iterator[TokenUsage]:
    for path in iter_session_files(root):
        yield from _iter_file_token_usage(path)


def _iter_file_events(path: Path) -> Iterator[SessionEvent]:
    session = _json_dict(path)
    session_id = _as_str(session.get("sessionId"))
    project_dir = _project_dir(path)

    messages = session.get("messages")
    if not isinstance(messages, list):
        return

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = _role(message.get("type"))
        if role is None:
            continue

        timestamp = _as_str(message.get("timestamp"))
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

        tool_calls = message.get("toolCalls")
        if not isinstance(tool_calls, list):
            continue

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            name = _as_str(call.get("name"))
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="tool_use",
                timestamp=_as_str(call.get("timestamp")) or timestamp,
                project_dir=project_dir,
                name=name,
                input=_dict_or_empty(call.get("args")),
            )

            result_text = _tool_result_text(call)
            if result_text:
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=session_id,
                    source_path=path,
                    role="tool",
                    kind="tool_result",
                    timestamp=_as_str(call.get("timestamp")) or timestamp,
                    project_dir=project_dir,
                    name=name,
                    text=result_text,
                )


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session = _json_dict(path)
    session_id = _as_str(session.get("sessionId"))
    project_dir = _project_dir(path)

    messages = session.get("messages")
    if not isinstance(messages, list):
        return

    for message in messages:
        if not isinstance(message, dict):
            continue
        tokens = _dict_or_empty(message.get("tokens"))
        if not tokens:
            continue

        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=_as_str(message.get("timestamp")),
            project_dir=project_dir,
            model=_as_str(message.get("model")),
            input_tokens=_as_int(tokens.get("input")),
            output_tokens=_as_int(tokens.get("output")),
            reasoning_tokens=_as_int(tokens.get("thoughts")),
            cache_read_tokens=_as_int(tokens.get("cached")),
            total_tokens=_optional_int(tokens.get("total")),
        )


def _project_dir(path: Path) -> str | None:
    project_root = path.parent.parent / ".project_root"
    try:
        value = project_root.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _tool_result_text(call: dict[str, Any]) -> str | None:
    result_display = _as_str(call.get("resultDisplay"))
    if result_display:
        return result_display.strip()
    result = call.get("result")
    text = extract_text(result).strip()
    return text or None


def _role(value: object) -> str | None:
    if value == "user":
        return "user"
    if value == "gemini":
        return "assistant"
    return None


def _json_dict(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
