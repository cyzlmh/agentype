from pathlib import Path

from agentype.analysis import (
    Discovery,
    DISCOVERY_SYSTEM_PROMPT,
    ThemeScore,
    agentype_overview_from_dict,
    _discovery_payload,
    _parse_discovery,
    build_agentype_overview,
    build_usage_report,
)
from agentype.collector import ProjectDocument, SkillInfo, collect_usage
from agentype.sources.base import SessionEvent, TokenUsage


def test_build_usage_report_summarizes_agents_periods_and_tools() -> None:
    events = [
        SessionEvent(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            role="user",
            kind="message",
            timestamp="2026-04-30T01:00:00Z",
            project_dir="/repo/agentype",
            text="add report",
        ),
        SessionEvent(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:01:00Z",
            project_dir="/repo/agentype",
            name="exec_command",
        ),
        SessionEvent(
            provider="nanobot",
            session_id="n1",
            source_path=Path("nano.jsonl"),
            role="user",
            kind="message",
            timestamp="2026-05-01T01:00:00Z",
            project_dir="/repo/workspace",
            text="summarize",
        ),
    ]
    usage = [
        TokenUsage(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            timestamp="2026-04-30T01:02:00Z",
            project_dir="/repo/agentype",
            total_tokens=100,
            cache_read_tokens=50,
        ),
        TokenUsage(
            provider="nanobot",
            session_id="n1",
            source_path=Path("nano.jsonl"),
            timestamp="2026-05-01T01:02:00Z",
            project_dir="/repo/workspace",
            total_tokens=200,
            cost=0.25,
        ),
    ]

    report = build_usage_report(events, usage)

    assert [item.provider for item in report.providers] == ["nanobot", "codex"]
    assert report.providers[0].prompts == 1
    assert report.providers[0].non_cache_tokens == 200
    assert report.providers[1].tokens_with_cache == 150
    assert report.tools[0].name == "exec_command"
    assert report.monthly[0].period == "2026-04"
    assert report.monthly[0].events == 2
    assert report.monthly[0].prompts == 1
    assert report.monthly[0].sessions == 1
    assert report.monthly[0].tokens_with_cache == 150
    assert report.monthly[1].period == "2026-05"
    assert report.projects[0].project == "workspace"
    assert report.overall.tokens_with_cache == 350
    assert report.overall.non_cache_tokens == 300
    assert report.overall.cache_tokens == 50
    assert report.overall.active_days == 2
    assert report.confidence[0].score > 0


def test_build_usage_report_handles_missing_metadata_confidence() -> None:
    events = [
        SessionEvent(
            provider="agent",
            session_id=None,
            source_path=Path("session.jsonl"),
            role="assistant",
            kind="message",
        )
    ]

    report = build_usage_report(events, [])

    assert report.providers[0].provider == "agent"
    assert report.providers[0].events == 1
    assert report.providers[0].confidence < 0.5
    assert report.confidence[0].timestamp_coverage == 0
    assert report.confidence[0].project_coverage == 0


def test_build_usage_report_merges_models_by_model_id() -> None:
    report = build_usage_report(
        [],
        [
            TokenUsage(provider="claude", source_path=Path("a.jsonl"), model="glm-5", total_tokens=100),
            TokenUsage(provider="nanobot", source_path=Path("b.jsonl"), model="glm-5", total_tokens=200),
        ],
    )

    assert len(report.models) == 1
    assert report.models[0].model == "glm-5"
    assert report.models[0].records == 2
    assert report.models[0].tokens_with_cache == 300


def test_build_agentype_overview_uses_llm_discovery_without_domain_mapping() -> None:
    events = [
        SessionEvent(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            role="user",
            kind="message",
            timestamp="2026-04-30T01:00:00Z",
            project_dir="/repo/agentype",
        ),
        SessionEvent(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:01:00Z",
            project_dir="/repo/agentype",
            name="exec_command",
        ),
        SessionEvent(
            provider="claude",
            session_id="c2",
            source_path=Path("claude.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:02:00Z",
            project_dir="/repo/agentype",
            name="Edit",
        ),
    ]
    events.extend(
        SessionEvent(
            provider="codex",
            session_id=f"c{i}",
            source_path=Path(f"codex-{i}.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T01:03:00Z",
            project_dir="/repo/agentype",
            name="exec_command",
        )
        for i in range(120)
    )
    usage = [
        TokenUsage(
            provider="codex",
            session_id="c1",
            source_path=Path("codex.jsonl"),
            timestamp="2026-04-30T01:02:00Z",
            project_dir="/repo/agentype",
            total_tokens=1000,
        )
    ]

    skills = {
        "cli-creator": SkillInfo(
            name="cli-creator",
            description="Create Python Click CLIs and command-line development tools.",
            use_count=10,
            projects=["/repo/agentype"],
        )
    }

    discovery = Discovery(
        archetype="The Workflow Cartographer",
        description="CLI toolmaking and local automation",
        keywords=["agent skill maintenance"],
        comment="You are a workflow cartographer using local automation.",
        themes=[
            ThemeScore(
                name="CLI toolmaking and local automation",
                score=0.7,
                share=0.7,
                evidence=["cli-creator skill signal"],
            )
        ],
    )
    overview = build_agentype_overview(build_usage_report(events, usage, skills), discovery)

    assert overview.description == "CLI toolmaking and local automation"
    assert overview.archetype == "The Workflow Cartographer"
    assert overview.top_agents[0] == "codex"
    assert overview.themes[0].evidence == ["cli-creator skill signal"]


def test_build_usage_report_extracts_skill_discovery_signals() -> None:
    events = [
        SessionEvent(
            provider="claude",
            session_id="s1",
            source_path=Path("claude.jsonl"),
            role="user",
            kind="message",
            timestamp="2026-04-30T01:00:00Z",
            project_dir="/repo/newsroom",
            text="fact check the interview transcript and draft article headline",
        ),
        SessionEvent(
            provider="claude",
            session_id="s2",
            source_path=Path("claude-2.jsonl"),
            role="user",
            kind="message",
            timestamp="2026-04-30T02:00:00Z",
            project_dir="/repo/newsroom",
            text="summarize interview notes and extract direct quotes for the article",
        ),
        SessionEvent(
            provider="claude",
            session_id="s2",
            source_path=Path("claude-2.jsonl"),
            role="assistant",
            kind="tool_use",
            timestamp="2026-04-30T02:01:00Z",
            project_dir="/repo/newsroom",
            name="Skill",
            input={"skill": "content-summarize"},
        ),
    ]
    skills = {
        "content-summarize": SkillInfo(
            name="content-summarize",
            description="Summarize articles, interviews, notes, and transcripts from ~/private/archive.",
        )
    }
    collect_usage(skills, events)

    report = build_usage_report(events, [], skills)

    assert report.signals.installed_skills == 1
    assert report.signals.used_skills == 1
    assert report.signals.skill_events == 1
    assert report.signals.skills[0].name == "content-summarize"
    assert report.signals.skills[0].explicit_uses == 1
    assert report.signals.skills[0].description.startswith("Summarize articles")
    assert "~/private" not in report.signals.skills[0].description


def test_discovery_payload_includes_deterministic_text_context() -> None:
    events = [
        SessionEvent(
            provider="codex",
            session_id="s1",
            source_path=Path("session.jsonl"),
            role="assistant",
            kind="tool_use",
            project_dir="/repo/agentype",
            name="Skill",
            input={"skill": "cli-creator"},
        )
    ]
    skills = {
        "cli-creator": SkillInfo(
            name="cli-creator",
            description="Create Python Click CLIs.",
            category="development",
            use_count=1,
            canonical_paths=["/home/user/.agents/skills/cli-creator/SKILL.md"],
        )
    }
    documents = [
        ProjectDocument(
            project="agentype",
            project_dir="/repo/agentype",
            filename="README.md",
            path="/repo/agentype/README.md",
            text="Python CLI that analyzes local AI-agent usage.",
        )
    ]

    usage = [
        TokenUsage(
            provider="codex",
            source_path=Path("usage.jsonl"),
            timestamp="2026-04-30T01:00:00Z",
            project_dir="/repo/agentype",
            model="glm-5",
            total_tokens=1000,
        )
    ]
    report = build_usage_report(events, usage, skills, documents)
    payload = _discovery_payload(report)

    assert payload["usage_summary"] == {
        "tokens_used_last_30_days": 1000,
        "used_agents": ["codex"],
        "used_models": ["glm-5"],
    }
    assert "usage" not in payload
    assert "top_projects" not in payload
    assert "top_agents" not in payload
    assert "top_models" not in payload
    assert payload["skill_discovery"]["top_skills"][0]["category"] == "development"
    assert payload["skill_discovery"]["top_skills"][0]["canonical_paths"][0].endswith("SKILL.md")
    assert payload["project_documents"][0]["filename"] == "README.md"
    assert "local AI-agent usage" in payload["project_documents"][0]["text"]


def test_parse_discovery_accepts_labeled_persona_text() -> None:
    discovery = _parse_discovery(
        """
        Archetype: Local Systems Cartographer
        Description: agent analytics
        Keywords: Python, agent analytics
        Comment: You are a local agent analytics builder.
        """
    )

    assert discovery.description == "agent analytics"
    assert discovery.keywords == ["Python", "agent analytics"]
    assert discovery.comment.startswith("You are a")


def test_parse_discovery_falls_back_to_first_line_and_raw_comment() -> None:
    discovery = _parse_discovery(
        "Builder\nYou are a tool builder who keeps the workflow small."
    )

    assert discovery.archetype == "Builder"
    assert discovery.description == "unknown"
    assert discovery.comment.startswith("Builder")


def test_discovery_prompt_requires_direct_persona_deduction() -> None:
    assert 'Start the comment with "You are a..."' in DISCOVERY_SYSTEM_PROMPT
    assert "Do not output JSON" in DISCOVERY_SYSTEM_PROMPT
    assert "industry/domain/theme" in DISCOVERY_SYSTEM_PROMPT
    assert "tech stack" in DISCOVERY_SYSTEM_PROMPT
    assert "special skills" in DISCOVERY_SYSTEM_PROMPT
    assert "AI usage patterns" in DISCOVERY_SYSTEM_PROMPT


def test_build_agentype_overview_without_discovery_is_deterministic_only() -> None:
    report = build_usage_report(
        [
            SessionEvent(
                provider="codex",
                session_id="c1",
                source_path=Path("codex.jsonl"),
                role="user",
                kind="message",
                timestamp="2026-04-30T01:00:00Z",
                project_dir="/repo/agentype",
            )
        ],
        [],
    )

    overview = build_agentype_overview(report)  # no discovery

    assert overview.archetype == ""
    assert overview.description == ""
    assert overview.keywords == []
    assert overview.comment == ""
    assert overview.themes == []
    assert overview.top_agents == ["codex"]

    data = overview.to_dict()
    assert "archetype" not in data
    assert "description" not in data
    assert "keywords" not in data
    assert "comment" not in data
    assert "themes" not in data
    assert "project_insights" not in data


def test_build_agentype_overview_json_keeps_populated_llm_fields() -> None:
    report = build_usage_report(
        [
            SessionEvent(
                provider="codex",
                session_id="c1",
                source_path=Path("codex.jsonl"),
                role="user",
                kind="message",
                timestamp="2026-04-30T01:00:00Z",
                project_dir="/repo/agentype",
            )
        ],
        [],
    )
    discovery = Discovery(
        archetype="Builder",
        description="agent analytics",
        keywords=["Python"],
        comment="You are an agent analytics builder.",
    )

    data = build_agentype_overview(report, discovery).to_dict()

    assert data["archetype"] == "Builder"
    assert data["description"] == "agent analytics"
    assert data["keywords"] == ["Python"]
    assert data["comment"] == "You are an agent analytics builder."
    assert "themes" not in data
    assert "project_insights" not in data


def test_agentype_overview_from_dict_loads_agent_augmented_json() -> None:
    report = build_usage_report(
        [
            SessionEvent(
                provider="codex",
                session_id="c1",
                source_path=Path("codex.jsonl"),
                role="user",
                kind="message",
                timestamp="2026-04-30T01:00:00Z",
                project_dir="/repo/agentype",
            )
        ],
        [
            TokenUsage(
                provider="codex",
                source_path=Path("usage.jsonl"),
                timestamp="2026-04-30T01:01:00Z",
                project_dir="/repo/agentype",
                model="glm-5",
                total_tokens=100,
            )
        ],
    )
    data = build_agentype_overview(report).to_dict()
    data.update(
        {
            "archetype": "Workflow Cartographer",
            "description": "local agent analytics",
            "keywords": ["Python", "CLI"],
            "comment": "You are a builder of compact agent workflows.",
        }
    )

    overview = agentype_overview_from_dict(data)

    assert overview.archetype == "Workflow Cartographer"
    assert overview.keywords == ["Python", "CLI"]
    assert overview.statistics.overall.tokens_with_cache == 100
    assert overview.statistics.providers[0].provider == "codex"


def test_skill_discovery_does_not_extract_prompt_keywords() -> None:
    report = build_usage_report(
        [
            SessionEvent(
                provider="codex",
                session_id="s2",
                source_path=Path("session-2.jsonl"),
                role="user",
                kind="message",
                text="compare interview notes and article structure",
            ),
        ],
        [],
    )

    assert report.signals.installed_skills == 0
    assert report.signals.used_skills == 0
    assert report.signals.skills == []
