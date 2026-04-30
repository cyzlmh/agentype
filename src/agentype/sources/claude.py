"""Read Claude Code sessions from local JSONL transcripts."""

from collections.abc import Iterator
from pathlib import Path

from .. import paths
from .base import SessionEvent, TokenUsage
from .utils import collect_jsonl_files, extract_text, iter_jsonl

PROVIDER = "claude"


def default_root() -> Path:
    return paths.claude_projects_dir()


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    base = root or default_root()
    for path in collect_jsonl_files(base):
        if path.name.startswith("agent-"):
            continue
        yield path


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
        session_id = session_id or _as_str(entry.get("sessionId"))
        project_dir = _as_str(entry.get("cwd")) or project_dir or path.parent.name
        timestamp = _as_str(entry.get("timestamp"))

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        role = _as_str(message.get("role")) or "unknown"
        content = message.get("content")

        text = extract_text(content).strip()
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

        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_input = block.get("input")
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="tool_use",
                timestamp=timestamp,
                project_dir=project_dir,
                name=_as_str(block.get("name")),
                input=tool_input if isinstance(tool_input, dict) else {},
            )


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session_id: str | None = None
    project_dir: str | None = None

    for entry in iter_jsonl(path):
        session_id = session_id or _as_str(entry.get("sessionId"))
        project_dir = _as_str(entry.get("cwd")) or project_dir or path.parent.name
        timestamp = _as_str(entry.get("timestamp"))

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue

        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=timestamp,
            project_dir=project_dir,
            model=_as_str(message.get("model")),
            input_tokens=_as_int(usage.get("input_tokens")),
            output_tokens=_as_int(usage.get("output_tokens")),
            cache_read_tokens=_as_int(usage.get("cache_read_input_tokens")),
            cache_write_tokens=_as_int(usage.get("cache_creation_input_tokens")),
        )


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
