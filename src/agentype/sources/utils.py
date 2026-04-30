"""Utilities shared by local session readers."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
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


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [extract_text(item) for item in value]
        return "\n".join(part for part in parts if part.strip())
    if isinstance(value, dict):
        if value.get("type") == "tool_use":
            return ""
        for key in ("text", "input_text", "output_text", "content"):
            text = extract_text(value.get(key))
            if text.strip():
                return text
    return ""


def collect_jsonl_files(root: Path, *, max_depth: int | None = None) -> list[Path]:
    files: list[Path] = []
    _collect_jsonl_files(root, files, depth=0, max_depth=max_depth)
    return files


def _collect_jsonl_files(
    root: Path,
    files: list[Path],
    *,
    depth: int,
    max_depth: int | None,
) -> None:
    if not root.exists() or (max_depth is not None and depth > max_depth):
        return

    try:
        entries = list(root.iterdir())
    except OSError:
        return

    for path in entries:
        if path.is_dir():
            _collect_jsonl_files(path, files, depth=depth + 1, max_depth=max_depth)
        elif path.suffix == ".jsonl":
            files.append(path)
