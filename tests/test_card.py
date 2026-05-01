from pathlib import Path

from PIL import Image

from agentype import _poster_text
from agentype.analysis import Discovery, ThemeScore, build_agentype_overview, build_usage_report
from agentype.card import QR_SIZE, _display_period, _github_qr, _trend_groups, render_overview_card
from agentype.sources.base import SessionEvent, TokenUsage


def _overview(discovery: Discovery | None = None):
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
        ],
        [
            TokenUsage(
                provider="codex",
                session_id="c1",
                source_path=Path("usage.jsonl"),
                timestamp="2026-04-30T01:02:00Z",
                project_dir="/repo/agentype",
                model="glm-5",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cache_read_tokens=50,
            )
        ],
    )
    return build_agentype_overview(report, discovery)


def test_poster_text_handles_no_llm_condition() -> None:
    text = _poster_text(_overview())

    assert "AGENTYPE" not in text
    assert "Usage Snapshot" in text
    assert "Deterministic local AI-agent usage summary" not in text
    assert "Top agents:" not in text


def test_render_overview_card_writes_png_for_llm_and_no_llm(tmp_path: Path) -> None:
    discovery = Discovery(
        archetype="AI Infrastructure Architect",
        description="multi-agent systems and LLM deployment",
        keywords=["LLM deployment", "multi-agent orchestration"],
        comment="You are an AI infrastructure builder focused on agent workflows.",
        themes=[
            ThemeScore(
                name="Agent Infrastructure",
                score=0.8,
                share=0.8,
                evidence=["agentype project"],
            )
        ],
    )

    no_llm_path = render_overview_card(_overview(), tmp_path / "no-llm.png")
    llm_path = render_overview_card(_overview(discovery), tmp_path / "llm.png")

    assert no_llm_path.read_bytes().startswith(b"\x89PNG")
    assert llm_path.read_bytes().startswith(b"\x89PNG")


def test_poster_uses_monthly_and_weekly_usage_trends() -> None:
    monthly, weekly = _trend_groups(_overview())

    assert monthly[0] == "Monthly"
    assert [item.period for item in monthly[1]] == ["2026-04"]
    assert weekly[0] == "Weekly"
    assert [_display_period(item.period) for item in weekly[1]] == ["2026-04-27..05-03"]


def test_github_qr_has_fixed_poster_size() -> None:
    qr = _github_qr()

    assert qr.size == (QR_SIZE, QR_SIZE)
    assert qr.mode == "RGB"


def test_render_overview_card_expands_for_long_llm_persona(tmp_path: Path) -> None:
    discovery = Discovery(
        archetype="AI Infrastructure Architect With Long Context",
        description=(
            "multi-agent infrastructure, local analytics, LLM deployment, "
            "workflow automation, and cross-provider observability"
        ),
        keywords=["LLM deployment", "multi-agent orchestration", "local analytics", "workflow automation"],
        comment=(
            "You are an AI infrastructure builder who moves between local telemetry, "
            "agent workflow design, deployment debugging, and model-provider integration. "
            "Your usage profile emphasizes practical systems work, repeated validation, "
            "and careful packaging of outputs for other agents and end users."
        ),
    )

    path = render_overview_card(_overview(discovery), tmp_path / "long.png")

    with Image.open(path) as img:
        assert img.size[0] == 1080
        assert img.size[1] > 1200


def test_render_overview_card_handles_non_ascii_persona(tmp_path: Path) -> None:
    discovery = Discovery(
        archetype="本地智能体工程师",
        description="多智能体工作流、私有数据分析、自动化发布",
        keywords=["本地优先", "智能体", "自动化"],
        comment="你是一个重视验证和可复现流程的本地智能体工程师。",
    )

    path = render_overview_card(_overview(discovery), tmp_path / "non-ascii.png")

    assert path.read_bytes().startswith(b"\x89PNG")
