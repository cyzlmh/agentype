"""Read Codex CLI sessions from local JSONL transcripts."""

from collections.abc import Iterator
from pathlib import Path

from .. import paths
from .base import SessionEvent, TokenUsage
from .utils import collect_jsonl_files, extract_text, iter_jsonl

PROVIDER = "codex"


def default_root() -> Path:
    return paths.codex_dir()


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    base = root or default_root()

    sessions_dir = base / "sessions"
    if sessions_dir.is_dir():
        yield from collect_jsonl_files(sessions_dir, max_depth=3)

    archived_dir = base / "archived_sessions"
    if archived_dir.is_dir():
        yield from sorted(archived_dir.glob("*.jsonl"))


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
        timestamp = _as_str(entry.get("timestamp"))
        event_type = entry.get("type")
        payload = entry.get("payload")

        if event_type == "session_meta" and isinstance(payload, dict):
            session_id = (
                _as_str(payload.get("id"))
                or _as_str(payload.get("session_id"))
                or _as_str(payload.get("sessionId"))
                or session_id
            )
            project_dir = _as_str(payload.get("cwd")) or project_dir
            continue

        if event_type != "response_item" or not isinstance(payload, dict):
            continue

        payload_type = payload.get("type")
        if payload_type == "message":
            text = extract_text(payload.get("content")).strip()
            if not text:
                continue
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=_as_str(payload.get("role")) or "unknown",
                kind="message",
                timestamp=timestamp,
                project_dir=project_dir,
                text=text,
            )
        elif payload_type == "function_call":
            arguments = payload.get("arguments")
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role="assistant",
                kind="tool_use",
                timestamp=timestamp,
                project_dir=project_dir,
                name=_as_str(payload.get("name")),
                input={"arguments": arguments} if arguments is not None else {},
            )
        elif payload_type == "function_call_output":
            output = _as_str(payload.get("output"))
            if output:
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=session_id,
                    source_path=path,
                    role="tool",
                    kind="tool_result",
                    timestamp=timestamp,
                    project_dir=project_dir,
                    text=output,
                )


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session_id: str | None = None
    project_dir: str | None = None

    for entry in iter_jsonl(path):
        timestamp = _as_str(entry.get("timestamp"))
        event_type = entry.get("type")
        payload = entry.get("payload")

        if event_type == "session_meta" and isinstance(payload, dict):
            session_id = (
                _as_str(payload.get("id"))
                or _as_str(payload.get("session_id"))
                or _as_str(payload.get("sessionId"))
                or session_id
            )
            project_dir = _as_str(payload.get("cwd")) or project_dir
            continue

        if event_type != "event_msg" or not isinstance(payload, dict):
            continue
        if payload.get("type") != "token_count":
            continue

        info = payload.get("info")
        if not isinstance(info, dict):
            continue
        usage = info.get("last_token_usage")
        if not isinstance(usage, dict):
            continue

        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=timestamp,
            project_dir=project_dir,
            input_tokens=_as_int(usage.get("input_tokens")),
            output_tokens=_as_int(usage.get("output_tokens")),
            reasoning_tokens=_as_int(usage.get("reasoning_output_tokens")),
            cache_read_tokens=_as_int(usage.get("cached_input_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
