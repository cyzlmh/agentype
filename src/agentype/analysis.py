"""Usage statistics and LLM-ready signal summaries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import json

from .collector import ProjectDocument, SkillInfo
from .llm import LlmConfig, chat
from .signals import AnalysisSignals, SkillSignal, build_analysis_signals
from .sources.base import SessionEvent, TokenUsage


@dataclass
class OverallStats:
    events: int = 0
    prompts: int = 0
    sessions: int = 0
    active_days: int = 0
    non_cache_tokens: int = 0
    cache_tokens: int = 0
    tokens_with_cache: int = 0


@dataclass
class ProviderStats:
    provider: str
    events: int = 0
    prompts: int = 0
    sessions: int = 0
    tool_uses: int = 0
    tool_results: int = 0
    token_records: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    non_cache_tokens: int = 0
    tokens_with_cache: int = 0
    confidence: float = 0.0


@dataclass
class PeriodStats:
    period: str
    events: int = 0
    prompts: int = 0
    sessions: int = 0
    non_cache_tokens: int = 0
    tokens_with_cache: int = 0


@dataclass
class ToolStats:
    name: str
    provider: str
    count: int = 0


@dataclass
class ProjectStats:
    project: str
    events: int = 0
    prompts: int = 0
    sessions: int = 0
    non_cache_tokens: int = 0
    tokens_with_cache: int = 0


@dataclass
class ModelStats:
    model: str
    records: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    non_cache_tokens: int = 0
    tokens_with_cache: int = 0


@dataclass
class ConfidenceStats:
    provider: str
    score: float
    events: int
    token_records: int
    timestamp_coverage: float
    project_coverage: float
    token_session_coverage: float
    tool_signal: float


@dataclass
class UsageReport:
    overall: OverallStats
    providers: list[ProviderStats]
    projects: list[ProjectStats]
    models: list[ModelStats]
    tools: list[ToolStats]
    signals: AnalysisSignals
    project_documents: list[ProjectDocument]
    daily: list[PeriodStats]
    weekly: list[PeriodStats]
    monthly: list[PeriodStats]
    confidence: list[ConfidenceStats]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ThemeScore:
    name: str
    score: float
    share: float
    evidence: list[str]


@dataclass
class ProjectInsight:
    name: str
    description: str
    tech_stack: list[str]
    industry: str
    domain: str


@dataclass
class Discovery:
    archetype: str
    description: str
    keywords: list[str]
    comment: str
    themes: list[ThemeScore] = field(default_factory=list)
    project_insights: list[ProjectInsight] = field(default_factory=list)
    available: bool = True
    error: str | None = None


@dataclass
class AgentypeOverview:
    archetype: str
    description: str
    keywords: list[str]
    comment: str
    usage_line: str
    trend_line: str
    top_agents: list[str]
    top_projects: list[str]
    top_models: list[str]
    top_tools: list[str]
    themes: list[ThemeScore]
    project_insights: list[ProjectInsight]
    confidence: float
    statistics: UsageReport

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("archetype", "description", "keywords", "comment", "themes", "project_insights"):
            if not data.get(key):
                data.pop(key, None)
        return data


def agentype_overview_from_dict(data: dict[str, object]) -> AgentypeOverview:
    """Load an overview previously written by Agentype and optionally augmented by an agent."""
    statistics = data.get("statistics")
    if not isinstance(statistics, dict):
        raise ValueError("Agentype JSON is missing a statistics object")

    return AgentypeOverview(
        archetype=_as_text(data.get("archetype")),
        description=_as_text(data.get("description")),
        keywords=_as_text_list(data.get("keywords")),
        comment=_as_text(data.get("comment")),
        usage_line=_as_text(data.get("usage_line")),
        trend_line=_as_text(data.get("trend_line")),
        top_agents=_as_text_list(data.get("top_agents")),
        top_projects=_as_text_list(data.get("top_projects")),
        top_models=_as_text_list(data.get("top_models")),
        top_tools=_as_text_list(data.get("top_tools")),
        themes=_theme_scores_from_dict(data.get("themes")),
        project_insights=_project_insights_from_dict(data.get("project_insights")),
        confidence=_as_float(data.get("confidence")),
        statistics=_usage_report_from_dict(statistics),
    )


def _usage_report_from_dict(data: dict[str, object]) -> UsageReport:
    return UsageReport(
        overall=_overall_stats_from_dict(data.get("overall")),
        providers=_provider_stats_from_dict(data.get("providers")),
        projects=_project_stats_from_dict(data.get("projects")),
        models=_model_stats_from_dict(data.get("models")),
        tools=_tool_stats_from_dict(data.get("tools")),
        signals=_analysis_signals_from_dict(data.get("signals")),
        project_documents=_project_documents_from_dict(data.get("project_documents")),
        daily=_period_stats_from_dict(data.get("daily")),
        weekly=_period_stats_from_dict(data.get("weekly")),
        monthly=_period_stats_from_dict(data.get("monthly")),
        confidence=_confidence_stats_from_dict(data.get("confidence")),
    )


def _overall_stats_from_dict(value: object) -> OverallStats:
    data = _dict_or_empty(value)
    return OverallStats(
        events=_as_int(data.get("events")),
        prompts=_as_int(data.get("prompts")),
        sessions=_as_int(data.get("sessions")),
        active_days=_as_int(data.get("active_days")),
        non_cache_tokens=_as_int(data.get("non_cache_tokens")),
        cache_tokens=_as_int(data.get("cache_tokens")),
        tokens_with_cache=_as_int(data.get("tokens_with_cache")),
    )


def _provider_stats_from_dict(value: object) -> list[ProviderStats]:
    rows = []
    for data in _dict_list(value):
        rows.append(
            ProviderStats(
                provider=_as_text(data.get("provider")),
                events=_as_int(data.get("events")),
                prompts=_as_int(data.get("prompts")),
                sessions=_as_int(data.get("sessions")),
                tool_uses=_as_int(data.get("tool_uses")),
                tool_results=_as_int(data.get("tool_results")),
                token_records=_as_int(data.get("token_records")),
                input_tokens=_as_int(data.get("input_tokens")),
                output_tokens=_as_int(data.get("output_tokens")),
                reasoning_tokens=_as_int(data.get("reasoning_tokens")),
                non_cache_tokens=_as_int(data.get("non_cache_tokens")),
                tokens_with_cache=_as_int(data.get("tokens_with_cache")),
                confidence=_as_float(data.get("confidence")),
            )
        )
    return rows


def _period_stats_from_dict(value: object) -> list[PeriodStats]:
    return [
        PeriodStats(
            period=_as_text(data.get("period")),
            events=_as_int(data.get("events")),
            prompts=_as_int(data.get("prompts")),
            sessions=_as_int(data.get("sessions")),
            non_cache_tokens=_as_int(data.get("non_cache_tokens")),
            tokens_with_cache=_as_int(data.get("tokens_with_cache")),
        )
        for data in _dict_list(value)
    ]


def _tool_stats_from_dict(value: object) -> list[ToolStats]:
    return [
        ToolStats(
            name=_as_text(data.get("name")),
            provider=_as_text(data.get("provider")),
            count=_as_int(data.get("count")),
        )
        for data in _dict_list(value)
    ]


def _project_stats_from_dict(value: object) -> list[ProjectStats]:
    return [
        ProjectStats(
            project=_as_text(data.get("project")),
            events=_as_int(data.get("events")),
            prompts=_as_int(data.get("prompts")),
            sessions=_as_int(data.get("sessions")),
            non_cache_tokens=_as_int(data.get("non_cache_tokens")),
            tokens_with_cache=_as_int(data.get("tokens_with_cache")),
        )
        for data in _dict_list(value)
    ]


def _model_stats_from_dict(value: object) -> list[ModelStats]:
    return [
        ModelStats(
            model=_as_text(data.get("model")),
            records=_as_int(data.get("records")),
            input_tokens=_as_int(data.get("input_tokens")),
            output_tokens=_as_int(data.get("output_tokens")),
            reasoning_tokens=_as_int(data.get("reasoning_tokens")),
            non_cache_tokens=_as_int(data.get("non_cache_tokens")),
            tokens_with_cache=_as_int(data.get("tokens_with_cache")),
        )
        for data in _dict_list(value)
    ]


def _confidence_stats_from_dict(value: object) -> list[ConfidenceStats]:
    return [
        ConfidenceStats(
            provider=_as_text(data.get("provider")),
            score=_as_float(data.get("score")),
            events=_as_int(data.get("events")),
            token_records=_as_int(data.get("token_records")),
            timestamp_coverage=_as_float(data.get("timestamp_coverage")),
            project_coverage=_as_float(data.get("project_coverage")),
            token_session_coverage=_as_float(data.get("token_session_coverage")),
            tool_signal=_as_float(data.get("tool_signal")),
        )
        for data in _dict_list(value)
    ]


def _analysis_signals_from_dict(value: object) -> AnalysisSignals:
    data = _dict_or_empty(value)
    return AnalysisSignals(
        installed_skills=_as_int(data.get("installed_skills")),
        used_skills=_as_int(data.get("used_skills")),
        skill_events=_as_int(data.get("skill_events")),
        skills=[
            SkillSignal(
                name=_as_text(item.get("name")),
                description=_as_text(item.get("description")),
                category=_as_text(item.get("category")),
                score=_as_float(item.get("score")),
                installed_count=_as_int(item.get("installed_count")),
                explicit_uses=_as_int(item.get("explicit_uses")),
                projects=_as_int(item.get("projects")),
                canonical_paths=_as_text_list(item.get("canonical_paths")),
            )
            for item in _dict_list(data.get("skills"))
        ],
    )


def _project_documents_from_dict(value: object) -> list[ProjectDocument]:
    return [
        ProjectDocument(
            project=_as_text(data.get("project")),
            project_dir=_as_text(data.get("project_dir")),
            filename=_as_text(data.get("filename")),
            path=_as_text(data.get("path")),
            text=_as_text(data.get("text")),
        )
        for data in _dict_list(value)
    ]


def _theme_scores_from_dict(value: object) -> list[ThemeScore]:
    return [
        ThemeScore(
            name=_as_text(data.get("name")),
            score=_as_float(data.get("score")),
            share=_as_float(data.get("share")),
            evidence=_as_text_list(data.get("evidence")),
        )
        for data in _dict_list(value)
    ]


def _project_insights_from_dict(value: object) -> list[ProjectInsight]:
    return [
        ProjectInsight(
            name=_as_text(data.get("name")),
            description=_as_text(data.get("description")),
            tech_stack=_as_text_list(data.get("tech_stack")),
            industry=_as_text(data.get("industry")),
            domain=_as_text(data.get("domain")),
        )
        for data in _dict_list(value)
    ]


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_or_empty(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def build_usage_report(
    events: list[SessionEvent],
    usage: list[TokenUsage],
    skills: dict[str, SkillInfo] | None = None,
    project_documents: list[ProjectDocument] | None = None,
) -> UsageReport:
    provider_sessions: dict[str, set[str]] = defaultdict(set)
    provider_events: dict[str, list[SessionEvent]] = defaultdict(list)
    provider_usage: dict[str, list[TokenUsage]] = defaultdict(list)

    provider_stats: dict[str, ProviderStats] = {}
    project_stats: dict[str, ProjectStats] = {}
    project_sessions: dict[str, set[str]] = defaultdict(set)
    model_stats: dict[str, ModelStats] = {}
    tool_counts: dict[tuple[str, str], int] = defaultdict(int)

    daily = defaultdict(PeriodStats)
    weekly = defaultdict(PeriodStats)
    monthly = defaultdict(PeriodStats)
    period_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)

    for event in events:
        provider_events[event.provider].append(event)
        stat = provider_stats.setdefault(event.provider, ProviderStats(provider=event.provider))
        stat.events += 1
        if event.kind == "message" and event.role == "user":
            stat.prompts += 1
        if event.kind == "tool_use":
            stat.tool_uses += 1
            if event.name:
                tool_counts[(event.provider, event.name)] += 1
        if event.kind == "tool_result":
            stat.tool_results += 1

        session_key = _session_key(event.provider, event.session_id, str(event.source_path))
        provider_sessions[event.provider].add(session_key)

        project = event.project_dir or "(unknown)"
        project = _project_name(project)
        project_stat = project_stats.setdefault(project, ProjectStats(project=project))
        project_stat.events += 1
        if event.kind == "message" and event.role == "user":
            project_stat.prompts += 1
        project_sessions[project].add(session_key)

        _add_event_to_periods(event, daily, weekly, monthly, period_sessions, session_key)

    for record in usage:
        provider_usage[record.provider].append(record)
        stat = provider_stats.setdefault(record.provider, ProviderStats(provider=record.provider))
        stat.token_records += 1
        stat.input_tokens += record.input_tokens
        stat.output_tokens += record.output_tokens
        stat.reasoning_tokens += record.reasoning_tokens
        stat.non_cache_tokens += record.non_cache_tokens
        stat.tokens_with_cache += record.tokens_with_cache

        project = _project_name(record.project_dir or "(unknown)")
        project_stat = project_stats.setdefault(project, ProjectStats(project=project))
        project_stat.non_cache_tokens += record.non_cache_tokens
        project_stat.tokens_with_cache += record.tokens_with_cache

        model_name = record.model or "(unknown)"
        model_stat = model_stats.setdefault(model_name, ModelStats(model=model_name))
        model_stat.records += 1
        model_stat.input_tokens += record.input_tokens
        model_stat.output_tokens += record.output_tokens
        model_stat.reasoning_tokens += record.reasoning_tokens
        model_stat.non_cache_tokens += record.non_cache_tokens
        model_stat.tokens_with_cache += record.tokens_with_cache

        _add_usage_to_periods(record, daily, weekly, monthly)

    confidence = _build_confidence(provider_events, provider_usage)
    confidence_by_provider = {item.provider: item.score for item in confidence}
    for provider, stat in provider_stats.items():
        stat.sessions = len(provider_sessions.get(provider, set()))
        stat.confidence = confidence_by_provider.get(provider, 0.0)

    for project, stat in project_stats.items():
        stat.sessions = len(project_sessions.get(project, set()))

    tools = [
        ToolStats(provider=provider, name=name, count=count)
        for (provider, name), count in tool_counts.items()
    ]

    overall = OverallStats(
        events=sum(item.events for item in provider_stats.values()),
        prompts=sum(item.prompts for item in provider_stats.values()),
        sessions=sum(item.sessions for item in provider_stats.values()),
        active_days=len(daily),
        non_cache_tokens=sum(item.non_cache_tokens for item in provider_stats.values()),
        cache_tokens=sum(item.tokens_with_cache - item.non_cache_tokens for item in provider_stats.values()),
        tokens_with_cache=sum(item.tokens_with_cache for item in provider_stats.values()),
    )

    signals = build_analysis_signals(events, skills)

    return UsageReport(
        overall=overall,
        providers=sorted(
            provider_stats.values(),
            key=lambda item: (item.tokens_with_cache, item.events, item.prompts),
            reverse=True,
        ),
        projects=sorted(
            project_stats.values(),
            key=lambda item: (item.tokens_with_cache, item.events),
            reverse=True,
        ),
        models=sorted(
            model_stats.values(),
            key=lambda item: (item.tokens_with_cache, item.records),
            reverse=True,
        ),
        tools=sorted(tools, key=lambda item: item.count, reverse=True),
        signals=signals,
        project_documents=project_documents or [],
        daily=_finalize_periods(daily, period_sessions, "daily"),
        weekly=_finalize_periods(weekly, period_sessions, "weekly"),
        monthly=_finalize_periods(monthly, period_sessions, "monthly"),
        confidence=confidence,
    )


def build_agentype_overview(report: UsageReport, discovery: Discovery | None = None) -> AgentypeOverview:
    if discovery is None or not discovery.available:
        archetype = ""
        description = ""
        keywords: list[str] = []
        comment = ""
        themes: list[ThemeScore] = []
        project_insights: list[ProjectInsight] = []
    else:
        archetype = discovery.archetype
        description = discovery.description
        keywords = discovery.keywords
        comment = discovery.comment
        themes = discovery.themes
        project_insights = discovery.project_insights

    top_agents = [item.provider for item in report.providers[:3]]
    top_projects = [item.project for item in report.projects if item.project != "(unknown)"][:5]
    top_models = [item.model for item in report.models if item.model != "(unknown)"][:5]
    top_tools = [item.name for item in report.tools[:5]]
    confidence = _average([item.score for item in report.confidence])
    usage_line = _usage_line(report)
    trend_line = _trend_line(report)

    return AgentypeOverview(
        archetype=archetype,
        description=description,
        keywords=keywords,
        comment=comment,
        usage_line=usage_line,
        trend_line=trend_line,
        top_agents=top_agents,
        top_projects=top_projects,
        top_models=top_models,
        top_tools=top_tools,
        themes=themes,
        project_insights=project_insights,
        confidence=round(confidence, 3),
        statistics=report,
    )


DISCOVERY_SYSTEM_PROMPT = """You are Agentype's analysis layer.

Infer a user's AI-work persona from aggregate local usage signals. Do not use a preset taxonomy. Do not assume the user is a developer, designer, researcher, or any other fixed type unless the evidence supports it.

Return ONLY plain text with these labels:
Archetype: short original persona label
Description: one concise phrase summarizing the interpreted industry/domain/theme
Keywords: comma-separated labels for notable industry, domain, tech stack, special skill, or AI usage signals
Comment: 2-3 concise sentences grounded in the evidence, starting with "You are a..."

Rules:
- Use project README/CLAUDE/AGENTS text to infer project description, tech stack, industry, and domain.
- Skill descriptions and categories are capability hints; explicit skill uses are stronger evidence.
- Deduce the persona from interpreted industry/domain/theme, tech stack, special skills, and AI usage patterns.
- Start the comment with "You are a..." and write it as a direct persona statement to the user.
- Keywords should be concise labels, not sentences.
- Do not output JSON, markdown tables, or code fences.
- Never mention raw private prompts because none are provided.
- Prefer saying "unknown" over guessing when project text is thin."""


def discover_usage(report: UsageReport, config: LlmConfig | None = None) -> Discovery:
    payload = _discovery_payload(report)
    prompt = "Analyze this aggregate local AI-agent usage profile:\n\n" + json.dumps(payload, indent=2)
    raw = chat(prompt, system=DISCOVERY_SYSTEM_PROMPT, max_tokens=2400, timeout=180, config=config)
    try:
        return _parse_discovery(raw)
    except (TypeError, ValueError, KeyError) as exc:
        raise RuntimeError(f"LLM discovery returned unusable persona text: {exc}") from exc


def unavailable_discovery(reason: str) -> Discovery:
    return Discovery(
        archetype="LLM discovery unavailable",
        description="unknown",
        keywords=[],
        comment=reason,
        themes=[],
        project_insights=[],
        available=False,
        error=reason,
    )


def _discovery_payload(report: UsageReport) -> dict[str, object]:
    return {
        "usage_summary": {
            "tokens_used_last_30_days": _last_30_day_tokens(report),
            "used_agents": [item.provider for item in report.providers if item.events or item.token_records],
            "used_models": [item.model for item in report.models if item.model != "(unknown)"],
        },
        "skill_discovery": {
            "installed": report.signals.installed_skills,
            "used": report.signals.used_skills,
            "use_events": report.signals.skill_events,
            "top_skills": [
                {
                    "name": item.name,
                    "explicit_uses": item.explicit_uses,
                    "projects": item.projects,
                    "installed_count": item.installed_count,
                    "category": item.category,
                    "description": item.description,
                    "canonical_paths": item.canonical_paths,
                }
                for item in report.signals.skills[:20]
            ],
        },
        "project_documents": [
            {
                "project": item.project,
                "filename": item.filename,
                "text": item.text,
            }
            for item in report.project_documents[:20]
        ],
    }


def _parse_discovery(raw: str) -> Discovery:
    text = raw.strip()
    if not text:
        raise ValueError("empty persona text")
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:])
        text = text.rsplit("```", 1)[0].strip()
    if text.startswith("{"):
        return _parse_legacy_json_discovery(text)

    fields = _parse_labeled_text(text)
    archetype = fields.get("archetype") or text.splitlines()[0].strip()
    description = fields.get("description") or fields.get("theme") or "unknown"
    keywords = _split_keywords(fields.get("keywords", ""))
    comment = fields.get("comment") or fields.get("explanation") or text
    return Discovery(
        archetype=archetype or "Unnamed persona",
        description=description,
        keywords=keywords,
        comment=comment,
    )


def _parse_labeled_text(text: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            label, value = stripped.split(":", 1)
            key = label.strip().lower().replace(" ", "_")
            if key in {"archetype", "description", "keywords", "comment", "explanation", "theme"}:
                current = key
                fields.setdefault(current, [])
                if value.strip():
                    fields[current].append(value.strip())
                continue
        if current:
            fields[current].append(stripped)
    return {key: " ".join(value).strip() for key, value in fields.items()}


def _split_keywords(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace("；", ",").replace(";", ",")
    return [item.strip(" -") for item in normalized.split(",") if item.strip(" -")][:8]


def _parse_legacy_json_discovery(text: str) -> Discovery:
    data = json.loads(_extract_json_object(text))
    themes = [
        ThemeScore(
            name=str(item.get("name", "unknown")),
            score=round(float(item.get("share", 0.0)), 3),
            share=round(float(item.get("share", 0.0)), 3),
            evidence=[str(value) for value in item.get("evidence", [])[:5]],
        )
        for item in data.get("themes", [])
        if isinstance(item, dict)
    ]
    description = str(data.get("description") or data.get("primary_theme") or (themes[0].name if themes else "unknown"))
    keywords = [str(value) for value in (data.get("keywords") or data.get("secondary_themes") or [])[:8]]
    if not keywords:
        keywords = [item.name for item in themes if item.name != description][:4]
    return Discovery(
        archetype=str(data.get("archetype") or "Unnamed persona"),
        description=description,
        keywords=keywords,
        comment=str(data.get("comment") or data.get("summary") or "LLM discovery returned no comment."),
        themes=themes,
    )


def _last_30_day_tokens(report: UsageReport) -> int:
    parsed: list[tuple[datetime, int]] = []
    for item in report.daily:
        try:
            day = datetime.strptime(item.period, "%Y-%m-%d")
        except ValueError:
            continue
        parsed.append((day, item.tokens_with_cache))
    if not parsed:
        return 0
    latest = max(day for day, _ in parsed)
    cutoff = latest - timedelta(days=29)
    return sum(tokens for day, tokens in parsed if day >= cutoff)


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _usage_line(report: UsageReport) -> str:
    overall = report.overall
    return (
        f"{overall.tokens_with_cache:,} tokens including cache "
        f"({overall.non_cache_tokens:,} non-cache), across {overall.prompts:,} prompts, "
        f"{overall.sessions:,} sessions, and {overall.active_days:,} active days."
    )


def _trend_line(report: UsageReport) -> str:
    if len(report.monthly) < 2:
        return "Not enough monthly history yet to describe a trend."
    latest = report.monthly[-1]
    previous = report.monthly[-2]
    if previous.tokens_with_cache <= 0:
        direction = "up"
    else:
        ratio = latest.tokens_with_cache / previous.tokens_with_cache
        if ratio >= 1.15:
            direction = "up"
        elif ratio <= 0.85:
            direction = "down"
        else:
            direction = "steady"
    peak = max(report.monthly, key=lambda item: item.tokens_with_cache)
    if direction == "up":
        return f"Usage is rising in {latest.period}; peak month so far is {peak.period}."
    if direction == "down":
        return f"Usage is lower in {latest.period}; peak month so far is {peak.period}."
    return f"Usage is steady in {latest.period}; peak month so far is {peak.period}."


def _build_confidence(
    provider_events: dict[str, list[SessionEvent]],
    provider_usage: dict[str, list[TokenUsage]],
) -> list[ConfidenceStats]:
    providers = set(provider_events) | set(provider_usage)
    results: list[ConfidenceStats] = []
    for provider in providers:
        events = provider_events.get(provider, [])
        usage = provider_usage.get(provider, [])
        event_count = len(events)
        usage_count = len(usage)
        session_keys = {_session_key(event.provider, event.session_id, str(event.source_path)) for event in events}
        usage_session_keys = {_session_key(record.provider, record.session_id, str(record.source_path)) for record in usage}

        timestamp_coverage = _coverage(
            sum(1 for event in events if event.timestamp)
            if event_count
            else sum(1 for record in usage if record.timestamp),
            event_count or usage_count,
        )
        project_coverage = _coverage(
            sum(1 for event in events if event.project_dir)
            if event_count
            else sum(1 for record in usage if record.project_dir),
            event_count or usage_count,
        )
        token_session_coverage = _coverage(len(usage_session_keys), len(session_keys)) if session_keys else float(bool(usage))
        tool_signal = min(sum(1 for event in events if event.kind == "tool_use") / 10, 1.0)
        volume = min((event_count + usage_count) / 100, 1.0)

        score = (
            volume * 0.25
            + timestamp_coverage * 0.20
            + project_coverage * 0.20
            + min(token_session_coverage, 1.0) * 0.25
            + tool_signal * 0.10
        )
        results.append(
            ConfidenceStats(
                provider=provider,
                score=round(score, 3),
                events=event_count,
                token_records=usage_count,
                timestamp_coverage=round(timestamp_coverage, 3),
                project_coverage=round(project_coverage, 3),
                token_session_coverage=round(min(token_session_coverage, 1.0), 3),
                tool_signal=round(tool_signal, 3),
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)


def _add_event_to_periods(
    event: SessionEvent,
    daily: dict[str, PeriodStats],
    weekly: dict[str, PeriodStats],
    monthly: dict[str, PeriodStats],
    period_sessions: dict[tuple[str, str], set[str]],
    session_key: str,
) -> None:
    for grain, target in (("daily", daily), ("weekly", weekly), ("monthly", monthly)):
        key = _period_key(event.timestamp, grain)
        if not key:
            continue
        stat = target.setdefault(key, PeriodStats(period=key))
        stat.events += 1
        if event.kind == "message" and event.role == "user":
            stat.prompts += 1
        period_sessions[(grain, key)].add(session_key)


def _add_usage_to_periods(
    record: TokenUsage,
    daily: dict[str, PeriodStats],
    weekly: dict[str, PeriodStats],
    monthly: dict[str, PeriodStats],
) -> None:
    for grain, target in (("daily", daily), ("weekly", weekly), ("monthly", monthly)):
        key = _period_key(record.timestamp, grain)
        if not key:
            continue
        stat = target.setdefault(key, PeriodStats(period=key))
        stat.non_cache_tokens += record.non_cache_tokens
        stat.tokens_with_cache += record.tokens_with_cache


def _finalize_periods(
    periods: dict[str, PeriodStats],
    period_sessions: dict[tuple[str, str], set[str]],
    grain: str,
) -> list[PeriodStats]:
    for key, stat in periods.items():
        stat.sessions = len(period_sessions.get((grain, key), set()))
    return sorted(periods.values(), key=lambda item: item.period)


def _period_key(timestamp: str | None, grain: str) -> str | None:
    parsed = _parse_timestamp(timestamp)
    if not parsed:
        return None
    if grain == "daily":
        return parsed.strftime("%Y-%m-%d")
    if grain == "weekly":
        year, week, _ = parsed.isocalendar()
        return f"{year}-W{week:02d}"
    if grain == "monthly":
        return parsed.strftime("%Y-%m")
    raise ValueError(f"Unknown period grain: {grain}")


def _parse_timestamp(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    normalized = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _session_key(provider: str, session_id: str | None, source_path: str) -> str:
    return f"{provider}:{session_id or source_path}"


def _project_name(project: str) -> str:
    if project == "(unknown)":
        return project
    return project.rstrip("/").split("/")[-1] or project


def _coverage(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return count / total
