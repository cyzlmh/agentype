"""Shared data shapes for agent session readers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionMeta:
    provider: str
    session_id: str
    source_path: Path
    project_dir: str | None = None
    created_at: str | None = None
    last_active_at: str | None = None
    title: str | None = None


@dataclass
class SessionEvent:
    provider: str
    session_id: str | None
    source_path: Path
    role: str
    kind: str
    timestamp: str | None = None
    project_dir: str | None = None
    name: str | None = None
    text: str | None = None
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    provider: str
    source_path: Path
    session_id: str | None = None
    timestamp: str | None = None
    project_dir: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int | None = None
    cost: float | None = None

    @property
    def non_cache_tokens(self) -> int:
        if self.total_tokens is not None:
            return self.total_tokens
        return self.input_tokens + self.output_tokens + self.reasoning_tokens

    @property
    def cache_tokens(self) -> int:
        return self.cache_read_tokens + self.cache_write_tokens

    @property
    def tokens_with_cache(self) -> int:
        return self.non_cache_tokens + self.cache_tokens
