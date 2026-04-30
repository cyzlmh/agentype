"""Skill-discovery signals for local agent usage analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .collector import SkillInfo
from .sources.base import SessionEvent

TOP_SIGNAL_LIMIT = 40


@dataclass
class SkillSignal:
    name: str
    description: str
    category: str
    score: float
    installed_count: int
    explicit_uses: int
    projects: int
    canonical_paths: list[str]


@dataclass
class AnalysisSignals:
    installed_skills: int
    used_skills: int
    skill_events: int
    skills: list[SkillSignal]


def build_analysis_signals(
    events: list[SessionEvent],
    skills: dict[str, SkillInfo] | None = None,
) -> AnalysisSignals:
    skills = skills or {}
    skill_events = sum(1 for event in events if _is_skill_event(event))
    rows = [_skill_signal(skill) for skill in skills.values()]

    rows.sort(
        key=lambda item: (
            item.explicit_uses > 0,
            item.score,
            item.projects,
            item.name,
        ),
        reverse=True,
    )

    return AnalysisSignals(
        installed_skills=sum(1 for skill in skills.values() if skill.install_count > 0),
        used_skills=sum(1 for skill in skills.values() if skill.use_count > 0),
        skill_events=skill_events,
        skills=rows[:TOP_SIGNAL_LIMIT],
    )


def _skill_signal(skill: SkillInfo) -> SkillSignal:
    score = skill.use_count * 5.0 + len(skill.projects) * 1.5 + skill.install_count * 0.5
    return SkillSignal(
        name=skill.name,
        description=_clean_description(skill.description),
        category=_clean_description(skill.category),
        score=round(score, 3),
        installed_count=skill.install_count,
        explicit_uses=skill.use_count,
        projects=len(skill.projects),
        canonical_paths=skill.canonical_paths[:5],
    )


def _is_skill_event(event: SessionEvent) -> bool:
    if event.kind != "tool_use" or event.name != "Skill":
        return False
    skill_name = event.input.get("skill", "")
    return isinstance(skill_name, str) and bool(skill_name)


def _clean_description(value: str) -> str:
    text = value.strip().replace("\n", " ")
    text = re.sub(r"/(?:Users|home)/[^\s,.;:)]+", "<path>", text)
    text = re.sub(r"~/[^\s,.;:)]+", "<path>", text)
    text = re.sub(r"[A-Za-z]:\\[^\s,.;:)]+", "<path>", text)
    return text[:100]
