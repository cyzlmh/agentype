import json
from pathlib import Path

from click.testing import CliRunner

from agentype import main
from agentype.analysis import Discovery, build_agentype_overview, build_usage_report
from agentype.sources.base import SessionEvent, TokenUsage


def test_cli_renders_agent_augmented_json_without_collecting(tmp_path: Path) -> None:
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
    overview = build_agentype_overview(
        report,
        Discovery(
            archetype="Workflow Cartographer",
            description="local agent analytics",
            keywords=["Python", "CLI"],
            comment="You are a builder of compact agent workflows.",
        ),
    )
    json_path = tmp_path / "agentype.json"
    json_path.write_text(json.dumps(overview.to_dict()), encoding="utf-8")

    result = CliRunner().invoke(main, ["--json-in", str(json_path), "--png-out", "--verbose", "--output", str(tmp_path)])

    assert result.exit_code == 0
    assert "Workflow Cartographer" in result.output
    assert "Verbose Analysis" in result.output
    assert (tmp_path / "agentype.png").read_bytes().startswith(b"\x89PNG")
