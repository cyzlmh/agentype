"""Collect installed skills and usage data from local agent sessions."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from . import paths
from .sources import (
    SessionEvent,
    TokenUsage,
    iter_claude_events,
    iter_claude_token_usage,
    iter_codex_events,
    iter_codex_token_usage,
    iter_gemini_events,
    iter_gemini_token_usage,
    iter_nanobot_compat_events,
    iter_nanobot_compat_token_usage,
    iter_nanobot_events,
    iter_nanobot_token_usage,
    iter_opencode_events,
    iter_opencode_token_usage,
    iter_openclaw_events,
    iter_openclaw_token_usage,
    iter_pi_events,
    iter_pi_token_usage,
)


@dataclass
class SkillInfo:
    name: str
    description: str
    category: str = ""
    install_count: int = 1
    use_count: int = 0
    last_used: str | None = None
    projects: list[str] = field(default_factory=list)
    canonical_paths: list[str] = field(default_factory=list)


@dataclass
class ProjectDocument:
    project: str
    project_dir: str
    filename: str
    path: str
    text: str


@dataclass(frozen=True)
class SkillRoot:
    agent: str
    path: Path
    project_dir: str | None = None


PROJECT_DOCUMENT_NAMES = ("README.md", "AGENTS.md", "CLAUDE.md")


def _skills_dir() -> Path:
    return paths.claude_skills_dir()


def _projects_dir() -> Path:
    return paths.claude_projects_dir()


def _codex_dir() -> Path:
    return paths.codex_dir()


def _opencode_dir() -> Path:
    return paths.opencode_data_dir()


def _pi_sessions_dir() -> Path:
    return paths.pi_sessions_dir()


def _gemini_dir() -> Path:
    return paths.gemini_dir()


def _openclaw_agents_dir() -> Path:
    return paths.openclaw_agents_dir()


def _nanobot_sessions_dir() -> Path:
    return paths.nanobot_sessions_dir()


def collect_installed_skills(project_dirs: Iterable[str] | None = None) -> dict[str, SkillInfo]:
    skills: dict[str, SkillInfo] = {}
    seen_paths: set[Path] = set()

    for root in _skill_roots(project_dirs):
        base = root.path
        if not base.exists():
            continue

        for skill_dir in base.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                skill_file = skill_dir / "skill.md"
            if not skill_file.exists():
                continue

            resolved = skill_file.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            post = frontmatter.load(str(skill_file))
            name = post.get("name") or skill_dir.name
            description = post.get("description") or str(post.content)[:300]
            category = post.get("category") or ""
            canonical_path = str(resolved)
            existing = skills.get(name)
            if existing:
                existing.install_count += 1
                if not existing.description and description:
                    existing.description = description
                if not existing.category and category:
                    existing.category = str(category)
                if canonical_path not in existing.canonical_paths:
                    existing.canonical_paths.append(canonical_path)
                if root.project_dir and root.project_dir not in existing.projects:
                    existing.projects.append(root.project_dir)
            else:
                projects = [root.project_dir] if root.project_dir else []
                skills[name] = SkillInfo(
                    name=name,
                    description=str(description),
                    category=str(category),
                    projects=projects,
                    canonical_paths=[canonical_path],
                )

    return skills


def collect_project_documents(
    project_dirs: Iterable[str],
    *,
    limit: int = 10,
    max_chars: int = 6000,
) -> list[ProjectDocument]:
    documents: list[ProjectDocument] = []
    seen_dirs: set[Path] = set()
    for value in project_dirs:
        project_dir = Path(value).expanduser()
        try:
            resolved_dir = project_dir.resolve()
        except OSError:
            resolved_dir = project_dir
        if resolved_dir in seen_dirs or not project_dir.is_dir():
            continue
        seen_dirs.add(resolved_dir)

        for filename in PROJECT_DOCUMENT_NAMES:
            path = project_dir / filename
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:max_chars].strip()
            except OSError:
                continue
            if not text:
                continue
            documents.append(
                ProjectDocument(
                    project=project_dir.name or str(project_dir),
                    project_dir=str(resolved_dir),
                    filename=filename,
                    path=str(path.resolve()),
                    text=text,
                )
            )
            if len(documents) >= limit:
                return documents
            break
    return documents


def _skill_roots(project_dirs: Iterable[str] | None) -> list[SkillRoot]:
    roots = [
        SkillRoot("agents", paths.agents_skills_dir()),
        SkillRoot("claude", _skills_dir()),
        SkillRoot("codex", paths.codex_skills_dir()),
    ]
    for project_dir in list(project_dirs or [])[:50]:
        project = Path(project_dir).expanduser()
        roots.extend(
            [
                SkillRoot("agents", project / ".agents" / "skills", str(project)),
                SkillRoot("claude", project / ".claude" / "skills", str(project)),
                SkillRoot("codex", project / ".codex" / "skills", str(project)),
            ]
        )
    return roots


def collect_session_events() -> list[SessionEvent]:
    return [
        event
        for _, source in session_event_sources()
        for event in source
    ]


def collect_token_usage() -> list[TokenUsage]:
    return [
        record
        for _, source in token_usage_sources()
        for record in source
    ]


def session_event_sources() -> list[tuple[str, Iterable[SessionEvent]]]:
    return [
        ("Claude Code", iter_claude_events(_projects_dir())),
        ("Codex", iter_codex_events(_codex_dir())),
        ("OpenCode", iter_opencode_events(_opencode_dir())),
        ("pi-agent", iter_pi_events(_pi_sessions_dir())),
        ("Gemini CLI", iter_gemini_events(_gemini_dir())),
        ("OpenClaw", iter_openclaw_events(_openclaw_agents_dir())),
        ("Nanobot", iter_nanobot_events(_nanobot_sessions_dir())),
        ("Nanobot-compatible", iter_nanobot_compat_events()),
    ]


def token_usage_sources() -> list[tuple[str, Iterable[TokenUsage]]]:
    return [
        ("Claude Code", iter_claude_token_usage(_projects_dir())),
        ("Codex", iter_codex_token_usage(_codex_dir())),
        ("OpenCode", iter_opencode_token_usage(_opencode_dir())),
        ("pi-agent", iter_pi_token_usage(_pi_sessions_dir())),
        ("Gemini CLI", iter_gemini_token_usage(_gemini_dir())),
        ("OpenClaw", iter_openclaw_token_usage(_openclaw_agents_dir())),
        ("Nanobot", iter_nanobot_token_usage(_nanobot_sessions_dir())),
        ("Nanobot-compatible", iter_nanobot_compat_token_usage()),
    ]


def summarize_token_usage(records: list[TokenUsage]) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for record in records:
        provider = summary.setdefault(
            record.provider,
            {
                "records": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "non_cache_tokens": 0,
                "tokens_with_cache": 0,
                "cost": 0.0,
            },
        )
        provider["records"] += 1
        provider["input_tokens"] += record.input_tokens
        provider["output_tokens"] += record.output_tokens
        provider["reasoning_tokens"] += record.reasoning_tokens
        provider["cache_read_tokens"] += record.cache_read_tokens
        provider["cache_write_tokens"] += record.cache_write_tokens
        provider["non_cache_tokens"] += record.non_cache_tokens
        provider["tokens_with_cache"] += record.tokens_with_cache
        if record.cost is not None:
            provider["cost"] += record.cost
    return summary


def collect_usage(
    skills: dict[str, SkillInfo],
    events: Iterable[SessionEvent] | None = None,
) -> dict[str, SkillInfo]:
    source = events if events is not None else iter_claude_events(_projects_dir())
    for event in source:
        _apply_skill_event(event, skills)

    return skills


def _apply_skill_event(event: SessionEvent, skills: dict[str, SkillInfo]) -> None:
    if event.kind != "tool_use" or event.name != "Skill":
        return

    skill_name = event.input.get("skill", "")
    if not isinstance(skill_name, str) or not skill_name:
        return

    if skill_name not in skills:
        skills[skill_name] = SkillInfo(
            name=skill_name,
            description="",
            install_count=0,
        )

    skill = skills[skill_name]
    skill.use_count += 1
    if event.timestamp and (skill.last_used is None or event.timestamp > skill.last_used):
        skill.last_used = event.timestamp

    project = event.project_dir
    if project and project not in skill.projects:
        skill.projects.append(project)


def collect_all() -> dict[str, SkillInfo]:
    skills = collect_installed_skills()
    collect_usage(skills)
    return skills
