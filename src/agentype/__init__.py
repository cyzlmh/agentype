import json
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from .analysis import (
    AgentypeOverview,
    UsageReport,
    agentype_overview_from_dict,
    build_agentype_overview,
    build_usage_report,
    discover_usage,
    unavailable_discovery,
)
from .card import render_overview_card
from .collector import (
    collect_installed_skills,
    collect_project_documents,
    collect_usage,
    session_event_sources,
    token_usage_sources,
)
from .llm import LlmConfig, config_for_llm
from .sources.base import SessionEvent, TokenUsage

console = Console()


@click.command()
@click.option("--output", "-o", default="output", help="Output directory")
@click.option("--json-out", is_flag=True, help="Save the full analysis as JSON")
@click.option("--json-in", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Render an existing Agentype JSON file")
@click.option("--png-out", is_flag=True, help="Save a shareable PNG summary")
@click.option("--verbose", "-v", is_flag=True, help="Show intermediate statistics and discovery evidence")
@click.option("--llm-base-url", default=None, help="OpenAI-compatible chat completions base URL. Env: AGENTYPE_LLM_BASE_URL")
@click.option("--llm-api-key", default=None, help="LLM API key. Env: AGENTYPE_LLM_API_KEY")
@click.option("--llm-model", default=None, help="LLM model ID. Env: AGENTYPE_LLM_MODEL")
def main(
    output: str,
    json_out: bool,
    json_in: Path | None,
    png_out: bool,
    verbose: bool,
    llm_base_url: str | None,
    llm_api_key: str | None,
    llm_model: str | None,
) -> None:
    """Analyze local AI-agent usage."""
    if json_in:
        overview = _load_overview_json(json_in)
        report = overview.statistics
    else:
        events, usage, report = _build_report_with_progress()
        llm_config = config_for_llm(base_url=llm_base_url, api_key=llm_api_key, model=llm_model)
        if llm_config:
            discovery = _discover_with_progress(report=report, config=llm_config)
        else:
            discovery = None
        overview = build_agentype_overview(report, discovery if discovery and discovery.available else None)

    _print_overview(overview)
    if verbose:
        _print_verbose(report, overview)

    if json_out:
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "agentype.json"
        path.write_text(json.dumps(overview.to_dict(), indent=2))
        console.print(f"[dim]Analysis saved to {path}[/]")
    if png_out:
        out_dir = Path(output)
        path = render_overview_card(overview, out_dir / "agentype.png")
        console.print(f"[dim]PNG saved to {path}[/]")


def _load_overview_json(path: Path) -> AgentypeOverview:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Could not parse Agentype JSON: {exc}") from exc
    except OSError as exc:
        raise click.ClickException(f"Could not read Agentype JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise click.ClickException("Agentype JSON must contain an object")
    try:
        return agentype_overview_from_dict(data)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _build_report_with_progress() -> tuple[list[SessionEvent], list[TokenUsage], UsageReport]:
    event_sources = session_event_sources()
    usage_sources = token_usage_sources()
    total_steps = len(event_sources) + len(usage_sources) + 3
    events: list[SessionEvent] = []
    usage: list[TokenUsage] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Collecting agent history...", total=total_steps)

        for name, source in event_sources:
            progress.update(task, description=f"Collecting {name} events...")
            records = list(source)
            events.extend(records)
            progress.update(task, advance=1, description=f"Collected {name} events ({len(records)})")

        for name, source in usage_sources:
            progress.update(task, description=f"Collecting {name} token usage...")
            records = list(source)
            usage.extend(records)
            progress.update(task, advance=1, description=f"Collected {name} token usage ({len(records)})")

        progress.update(task, description="Collecting installed skill metadata...")
        project_dirs = _top_project_dirs(events, usage)
        skills = collect_installed_skills(project_dirs)
        collect_usage(skills, events)
        progress.update(task, advance=1, description=f"Collected skill metadata ({len(skills)})")

        progress.update(task, description="Collecting top project text...")
        project_documents = collect_project_documents(project_dirs)
        progress.update(task, advance=1, description=f"Collected project documents ({len(project_documents)})")

        progress.update(task, description="Analyzing usage and work signals...")
        report = build_usage_report(events, usage, skills, project_documents)
        progress.update(task, advance=1, description="Analysis ready")

    return events, usage, report


def _top_project_dirs(events: list[SessionEvent], usage: list[TokenUsage], *, limit: int = 10) -> list[str]:
    scores: dict[str, dict[str, int]] = {}
    for event in events:
        if not event.project_dir:
            continue
        score = scores.setdefault(event.project_dir, {"tokens": 0, "events": 0})
        score["events"] += 1
    for record in usage:
        if not record.project_dir:
            continue
        score = scores.setdefault(record.project_dir, {"tokens": 0, "events": 0})
        score["tokens"] += record.tokens_with_cache
    return [
        project_dir
        for project_dir, _ in sorted(
            scores.items(),
            key=lambda item: (item[1]["tokens"], item[1]["events"], item[0]),
            reverse=True,
        )[:limit]
    ]


def _discover_with_progress(
    *,
    report: UsageReport,
    config: LlmConfig,
):
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Discovering persona with {config.model}...", total=1)
        try:
            discovery = discover_usage(report, config)
        except RuntimeError as exc:
            discovery = unavailable_discovery(str(exc))
        progress.update(task, advance=1, description="Discovery ready")
    if not discovery.available and discovery.error:
        console.print(f"[yellow]LLM discovery unavailable:[/] {discovery.error}")
    return discovery


def _print_overview(overview: AgentypeOverview) -> None:
    stats = overview.statistics.overall
    section = 1

    def print_section(title: str) -> None:
        nonlocal section
        console.print(f"[bold]{section}. {title}[/]")
        section += 1

    console.print()
    console.print(
        Panel(
            _poster_text(overview),
            subtitle="local AI-agent usage overview",
            border_style="violet" if overview.archetype else "cyan",
            padding=(1, 2),
        )
    )

    print_section("Token Usage")
    console.print(
        f"[bold]{_fmt_count(stats.tokens_with_cache)}[/] total with cache   "
        f"{_fmt_count(stats.non_cache_tokens)} non-cache   "
        f"{_fmt_count(stats.cache_tokens)} cache"
    )
    console.print(_stacked_token_bar(stats.non_cache_tokens, stats.cache_tokens, width=30))
    console.print(_token_io_line(overview.statistics))
    console.print(
        f"[dim]{_fmt_count(stats.prompts)} prompts · {_fmt_count(stats.sessions)} sessions · "
        f"{stats.active_days} active days · {_fmt_count(stats.events)} events[/]"
    )
    console.print()

    print_section("Breakdowns")
    _print_compact_rank_bars("Projects", [(item.project, item.tokens_with_cache) for item in overview.statistics.projects[:5]])
    _print_compact_rank_bars("Agents", [(item.provider, item.tokens_with_cache) for item in overview.statistics.providers[:5]])
    model_rows = [
        (item.model, item.tokens_with_cache)
        for item in overview.statistics.models
        if item.model != "(unknown)"
    ][:5]
    _print_compact_rank_bars("Models", model_rows)
    console.print()

    print_section("Usage Rhythm")
    _print_period_bars("Monthly", overview.statistics.monthly[-8:], width=34)
    _print_period_bars("Weekly", overview.statistics.weekly[-8:], width=34)
    console.print()

    if overview.themes:
        print_section("Discovered Themes")
        for theme in overview.themes[:6]:
            console.print(_ratio_bar(theme.name, int(theme.share * 1000), 1000, width=30, label=f"{theme.share:.0%}"))
            console.print(f"   [dim]{'; '.join(theme.evidence[:3])}[/]")
        console.print()


def _print_verbose(report: UsageReport, overview: AgentypeOverview) -> None:
    console.print("[bold]Verbose Analysis[/]")
    _print_overall_table(report)
    _print_period_table("Monthly Trend", report.monthly[-12:])
    _print_period_table("Weekly Trend", report.weekly[-8:])
    _print_period_table("Daily Trend", report.daily[-14:])
    _print_project_table(report, 12)
    _print_provider_table(report, 12)
    _print_model_table(report, 12)
    _print_tool_table(report, 12)
    if overview.archetype and overview.themes:
        _print_domain_table(overview)
    _print_confidence_table(report, 12)


def _print_overall_table(report: UsageReport) -> None:
    stats = report.overall
    table = Table(title="Overall Usage", show_header=True, header_style="bold cyan")
    table.add_column("Events", justify="right")
    table.add_column("Prompts", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Active Days", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Non-Cache", justify="right")
    table.add_column("Cache", justify="right")
    table.add_row(
        _fmt_count(stats.events),
        _fmt_count(stats.prompts),
        _fmt_count(stats.sessions),
        str(stats.active_days),
        _fmt_count(stats.tokens_with_cache),
        _fmt_count(stats.non_cache_tokens),
        _fmt_count(stats.cache_tokens),
    )
    console.print(table)


def _print_provider_table(report: UsageReport, limit: int) -> None:
    table = Table(title="Top Agents", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="cyan")
    table.add_column("Events", justify="right")
    table.add_column("Prompts", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Tools", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("With Cache", justify="right")
    for item in report.providers[:limit]:
        table.add_row(
            item.provider,
            _fmt_count(item.events),
            _fmt_count(item.prompts),
            _fmt_count(item.sessions),
            _fmt_count(item.tool_uses),
            _fmt_count(item.non_cache_tokens),
            _fmt_count(item.tokens_with_cache),
        )
    console.print(table)


def _print_model_table(report: UsageReport, limit: int) -> None:
    table = Table(title="Top Models", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="cyan")
    table.add_column("Records", justify="right")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Reasoning", justify="right")
    table.add_column("With Cache", justify="right")
    for item in report.models[:limit]:
        table.add_row(
            item.model,
            _fmt_count(item.records),
            _fmt_count(item.input_tokens),
            _fmt_count(item.output_tokens),
            _fmt_count(item.reasoning_tokens),
            _fmt_count(item.tokens_with_cache),
        )
    console.print(table)


def _print_project_table(report: UsageReport, limit: int) -> None:
    table = Table(title="Top Projects", show_header=True, header_style="bold cyan")
    table.add_column("Project", style="cyan")
    table.add_column("Events", justify="right")
    table.add_column("Prompts", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("With Cache", justify="right")
    for item in report.projects[:limit]:
        table.add_row(
            item.project,
            _fmt_count(item.events),
            _fmt_count(item.prompts),
            _fmt_count(item.sessions),
            _fmt_count(item.non_cache_tokens),
            _fmt_count(item.tokens_with_cache),
        )
    console.print(table)


def _print_period_table(title: str, rows: list) -> None:
    if not rows:
        return
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Period", style="cyan")
    table.add_column("Events", justify="right")
    table.add_column("Prompts", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("With Cache", justify="right")
    for item in rows:
        table.add_row(
            _display_period(item.period),
            _fmt_count(item.events),
            _fmt_count(item.prompts),
            _fmt_count(item.sessions),
            _fmt_count(item.non_cache_tokens),
            _fmt_count(item.tokens_with_cache),
        )
    console.print(table)


def _print_tool_table(report: UsageReport, limit: int) -> None:
    table = Table(title="Top Tools / Actions", show_header=True, header_style="bold cyan")
    table.add_column("Tool", style="cyan")
    table.add_column("Agent")
    table.add_column("Uses", justify="right")
    for item in report.tools[:limit]:
        table.add_row(item.name, item.provider, _fmt_count(item.count))
    console.print(table)


def _print_domain_table(overview: AgentypeOverview) -> None:
    table = Table(title="Discovered Themes", show_header=True, header_style="bold cyan")
    table.add_column("Theme", style="cyan")
    table.add_column("Share", justify="right")
    table.add_column("Evidence")
    for item in overview.themes:
        table.add_row(item.name, f"{item.share:.0%}", "; ".join(item.evidence[:4]))
    console.print(table)


def _print_confidence_table(report: UsageReport, limit: int) -> None:
    table = Table(title="Data Confidence", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Timestamps", justify="right")
    table.add_column("Projects", justify="right")
    table.add_column("Token Coverage", justify="right")
    table.add_column("Tool Signal", justify="right")
    for item in report.confidence[:limit]:
        table.add_row(
            item.provider,
            f"{item.score:.2f}",
            f"{item.timestamp_coverage:.0%}",
            f"{item.project_coverage:.0%}",
            f"{item.token_session_coverage:.0%}",
            f"{item.tool_signal:.0%}",
        )
    console.print(table)


def _fmt_count(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _join_or_dash(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def _poster_text(overview: AgentypeOverview) -> str:
    if overview.archetype:
        lines = [
            "[bold cyan]AGENTYPE[/]",
            f"[bold violet]{overview.archetype}[/]",
            f"[cyan]{overview.description}[/]",
        ]
        if overview.comment:
            lines.append(overview.comment)
        if overview.keywords:
            lines.append(f"[dim]Keywords: {_join_or_dash(overview.keywords)}[/]")
        return "\n".join(lines)

    return "[bold]Usage Snapshot[/]"


def _stacked_token_bar(non_cache: int, cache: int, *, width: int) -> str:
    total = non_cache + cache
    if total <= 0:
        return "tokens        " + "░" * width
    non_cache_width = round(non_cache / total * width)
    non_cache_width = max(1, min(width, non_cache_width)) if non_cache else 0
    cache_width = width - non_cache_width
    if cache and cache_width == 0:
        cache_width = 1
        non_cache_width = max(0, width - 1)
    bar = f"[cyan]{'█' * non_cache_width}[/][magenta]{'█' * cache_width}[/]"
    return f"mix          {bar}  [cyan]{non_cache / total:.0%} non-cache[/] / [magenta]{cache / total:.0%} cache[/]"


def _token_io_line(report: UsageReport) -> str:
    input_tokens = sum(item.input_tokens for item in report.providers)
    output_tokens = sum(item.output_tokens for item in report.providers)
    reasoning_tokens = sum(item.reasoning_tokens for item in report.providers)
    known = input_tokens + output_tokens + reasoning_tokens
    if known <= 0:
        return "[dim]Input/output token split is not available from these local records.[/]"
    return (
        f"known split   input {_fmt_count(input_tokens)} · output {_fmt_count(output_tokens)} · "
        f"reasoning {_fmt_count(reasoning_tokens)}"
    )


def _ratio_bar(
    name: str,
    value: int,
    total: int,
    *,
    width: int,
    name_width: int = 13,
    style: str = "cyan",
    label: str | None = None,
) -> str:
    ratio = value / total if total > 0 else 0
    filled = max(0, min(width, round(ratio * width)))
    if value > 0 and filled == 0:
        filled = 1
    bar = "█" * filled + "░" * (width - filled)
    suffix = label or _fmt_count(value)
    display_name = _fit_label(name, name_width)
    return f"{display_name:<{name_width}} [{style}]{bar}[/] {suffix}"


def _sparkline(values: list[int]) -> str:
    levels = "▁▂▃▄▅▆▇█"
    high = max(values)
    low = min(values)
    if high == low:
        return levels[-1] * len(values)
    return "".join(levels[round((value - low) / (high - low) * (len(levels) - 1))] for value in values)


def _print_period_bars(title: str, rows: list, *, width: int) -> None:
    if not rows:
        console.print(f"[cyan]{title}[/]: -")
        return
    console.print(f"[cyan]{title}[/] {_sparkline([item.tokens_with_cache for item in rows])}")
    total = max(item.tokens_with_cache for item in rows)
    for item in rows:
        console.print(
            f"  {_ratio_bar(_display_period(item.period), item.tokens_with_cache, total, width=width, name_width=19)}"
        )


def _print_compact_rank_bars(title: str, rows: list[tuple[str, int]]) -> None:
    if not rows:
        console.print(f"{title}: -")
        return
    console.print(f"[cyan]{title}[/]")
    total = max(value for _, value in rows)
    for name, value in rows:
        console.print(f"  {_ratio_bar(name, value, total, width=22, name_width=18)}")


def _fit_label(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "…"


def _display_period(period: str) -> str:
    if "-W" not in period:
        return period
    try:
        year_text, week_text = period.split("-W", 1)
        start = datetime.fromisocalendar(int(year_text), int(week_text), 1).date()
    except ValueError:
        return period
    end = start + timedelta(days=6)
    if start.year == end.year and start.month == end.month:
        return f"{start:%Y-%m-%d}..{end:%d}"
    return f"{start:%Y-%m-%d}..{end:%m-%d}"
