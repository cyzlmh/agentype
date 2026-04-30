"""Read Nanobot-compatible sessions from configured JSONL transcript roots."""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import SessionEvent, TokenUsage
from .utils import collect_jsonl_files

PROVIDER = "nanobot"


def default_roots() -> list[Path]:
    configured = os.environ.get("AGENTYPE_NANOBOT_ROOTS")
    if not configured:
        return []
    return [Path(os.path.expanduser(value)) for value in configured.split(os.pathsep) if value]


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    roots = _session_roots(root) if root is not None else default_roots()
    seen: set[Path] = set()

    for base in roots:
        for path in collect_jsonl_files(base):
            if path.name == "_active_sessions.json":
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def _session_roots(root: Path) -> list[Path]:
    if root.name == "sessions":
        return [root]

    roots: list[Path] = []
    direct = root / "sessions"
    if direct.is_dir():
        roots.append(direct)

    agents_dir = root / "agents"
    if agents_dir.is_dir():
        try:
            roots.extend(path / "sessions" for path in sorted(agents_dir.iterdir()) if path.is_dir())
        except OSError:
            pass

    return roots or [root]


def iter_events(root: Path | None = None) -> Iterator[SessionEvent]:
    for path in iter_session_files(root):
        yield from _iter_file_events(path)


def iter_token_usage(root: Path | None = None) -> Iterator[TokenUsage]:
    for path in iter_session_files(root):
        yield from _iter_file_token_usage(path)


def _iter_file_events(path: Path) -> Iterator[SessionEvent]:
    session_id = path.stem
    project_dir = _project_dir(path)

    for entry in _iter_file_entries(path):
        marker = entry.get("_type")
        if marker in {"metadata", "session_state"}:
            session_id = _as_str(entry.get("session_id")) or session_id
            continue

        role = _as_str(entry.get("role"))
        if not role:
            continue

        timestamp = _as_str(entry.get("timestamp"))

        if role == "tool":
            text = _as_str(entry.get("content"))
            if text:
                yield SessionEvent(
                    provider=PROVIDER,
                    session_id=session_id,
                    source_path=path,
                    role="tool",
                    kind="tool_result",
                    timestamp=timestamp,
                    project_dir=project_dir,
                    name=_as_str(entry.get("name")),
                    text=text,
                )
            continue

        content = _as_str(entry.get("content"))
        if content:
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="message",
                timestamp=timestamp,
                project_dir=project_dir,
                text=content,
            )

        tool_calls = entry.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue

        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            function = _dict_or_empty(call.get("function"))
            yield SessionEvent(
                provider=PROVIDER,
                session_id=session_id,
                source_path=path,
                role=role,
                kind="tool_use",
                timestamp=timestamp,
                project_dir=project_dir,
                name=_as_str(call.get("name")) or _as_str(function.get("name")),
                input=_parse_arguments(call.get("arguments") or function.get("arguments")),
            )


def _iter_file_token_usage(path: Path) -> Iterator[TokenUsage]:
    session_id = path.stem
    project_dir = _project_dir(path)

    for entry in _iter_file_entries(path):
        marker = entry.get("_type")
        if marker in {"metadata", "session_state"}:
            session_id = _as_str(entry.get("session_id")) or session_id
            continue

        payload = _dict_or_empty(entry.get("provider_payload"))
        usage = _dict_or_empty(payload.get("usage")) or _dict_or_empty(entry.get("usage"))
        if not usage:
            continue

        yield TokenUsage(
            provider=PROVIDER,
            source_path=path,
            session_id=session_id,
            timestamp=_as_str(entry.get("timestamp")),
            project_dir=project_dir,
            model=_as_str(entry.get("model"))
            or _as_str(payload.get("response_model"))
            or _as_str(payload.get("requested_model")),
            input_tokens=_as_int(usage.get("prompt_tokens") or usage.get("input_tokens") or usage.get("input")),
            output_tokens=_as_int(
                usage.get("completion_tokens") or usage.get("output_tokens") or usage.get("output")
            ),
            reasoning_tokens=_reasoning_tokens(usage),
            cache_read_tokens=_as_int(usage.get("cache_read_tokens") or usage.get("cached_input_tokens")),
            cache_write_tokens=_as_int(usage.get("cache_write_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens") or usage.get("totalTokens")),
        )


def _iter_file_entries(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def _project_dir(path: Path) -> str | None:
    for parent in path.parents:
        if parent.name == "sessions":
            return str(parent.parent)
    return None


def _parse_arguments(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"arguments": value}
        return parsed if isinstance(parsed, dict) else {"arguments": value}
    return {}


def _reasoning_tokens(usage: dict[str, Any]) -> int:
    details = _dict_or_empty(usage.get("completion_tokens_details"))
    return _as_int(details.get("reasoning_tokens") or usage.get("reasoning_tokens"))


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
