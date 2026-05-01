"""Render shareable Agentype terminal-style posters as PNG."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import qrcode

from .analysis import AgentypeOverview, PeriodStats

WIDTH = 1080
MIN_HEIGHT = 1200
LEGACY_HEIGHT = 1350
PAD = 72
CONTENT_WIDTH = WIDTH - PAD * 2

BG = "#050807"
PANEL = "#07130D"
BAR_BG = "#173321"
TEXT = "#D1FAE5"
MUTED = "#94A3B8"
FAINT = "#64748B"
GREEN = "#22C55E"
CYAN = "#38BDF8"
AMBER = "#F59E0B"
ROW_COLORS = ["#38BDF8", "#22C55E", "#F59E0B", "#A78BFA", "#F472B6"]
GITHUB_URL = "https://github.com/cyzlmh/agentype"
QR_SIZE = 132


def render_overview_card(
    overview: AgentypeOverview,
    output_path: str | Path = "output/agentype.png",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = _generated_timestamp()
    height = _measure_overview_height(overview, generated_at)
    img = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(img)
    _draw_overview(img, draw, overview, generated_at, height)

    img.save(str(output_path), "PNG")
    return output_path


def _measure_overview_height(overview: AgentypeOverview, generated_at: str) -> int:
    scratch = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(scratch)
    y = _layout_header(draw, overview, PAD, do_draw=False)
    y = _layout_token_block(draw, overview, y + 64, do_draw=False)
    y = _layout_breakdowns(draw, overview, y + 58, do_draw=False)
    y = _layout_usage_rhythm(draw, overview, y + 30, do_draw=False)
    y = _layout_footer(draw, generated_at, y + 34, do_draw=False)
    return max(MIN_HEIGHT, y + PAD)


def _draw_overview(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    overview: AgentypeOverview,
    generated_at: str,
    height: int,
) -> None:
    y = _layout_header(draw, overview, PAD, do_draw=True)
    y = _layout_token_block(draw, overview, y + 64, do_draw=True)
    y = _layout_breakdowns(draw, overview, y + 58, do_draw=True)
    y = _layout_usage_rhythm(draw, overview, y + 30, do_draw=True)
    _layout_footer(draw, generated_at, y + 34, do_draw=True, image=img)


def _layout_header(
    draw: ImageDraw.ImageDraw,
    overview: AgentypeOverview,
    y: int,
    *,
    do_draw: bool,
) -> int:
    command = "$ agentype --png-out"
    if do_draw:
        draw.text((PAD, y), command, font=_font(26), fill=FAINT)
    y += 54

    title = overview.archetype or "Usage Snapshot"
    title_font = _fit_font(draw, title, CONTENT_WIDTH, 62, 38, bold=True)
    if do_draw:
        draw.text((PAD, y), title, font=title_font, fill=GREEN)
    y += _text_height(draw, title, title_font) + 26

    if overview.archetype and overview.description:
        desc_font = _font(28)
        lines = _wrap_lines(draw, overview.description, desc_font, CONTENT_WIDTH)
        if do_draw:
            _draw_lines(draw, lines, PAD, y, desc_font, CYAN, 39)
        y += len(lines) * 39 + 26

    if overview.archetype and overview.comment:
        comment_font = _font(30)
        lines = _wrap_lines(draw, _clean_text(overview.comment), comment_font, CONTENT_WIDTH)
        if do_draw:
            _draw_lines(draw, lines, PAD, y, comment_font, TEXT, 42)
        y += len(lines) * 42 + 24

    if overview.archetype and overview.keywords:
        keyword_font = _font(21)
        lines = _wrap_lines(draw, "keywords: " + " / ".join(overview.keywords), keyword_font, CONTENT_WIDTH)
        if do_draw:
            _draw_lines(draw, lines, PAD, y, keyword_font, MUTED, 30)
        y += len(lines) * 30

    return y


def _layout_token_block(
    draw: ImageDraw.ImageDraw,
    overview: AgentypeOverview,
    y: int,
    *,
    do_draw: bool,
) -> int:
    stats = overview.statistics.overall
    panel_h = 268
    if do_draw:
        _panel(draw, y, panel_h)
        draw.text((PAD + 28, y + 28), "1. Token Usage", font=_font(27, bold=True), fill=GREEN)
        draw.text(
            (PAD + 28, y + 78),
            f"{_fmt_count(stats.tokens_with_cache)} total with cache",
            font=_font(36, bold=True),
            fill=TEXT,
        )
        draw.text(
            (PAD + 28, y + 126),
            f"{_fmt_count(stats.non_cache_tokens)} non-cache / {_fmt_count(stats.cache_tokens)} cache",
            font=_font(25),
            fill=MUTED,
        )

        bar_x = PAD + 28
        bar_y = y + 172
        _draw_stacked_bar(
            draw,
            bar_x,
            bar_y,
            CONTENT_WIDTH - 56,
            stats.non_cache_tokens,
            stats.cache_tokens,
            CYAN,
            GREEN,
            BAR_BG,
            height=22,
        )
        draw.text(
            (bar_x, bar_y + 40),
            f"{_fmt_count(stats.prompts)} prompts | {_fmt_count(stats.sessions)} sessions | "
            f"{stats.active_days} active days | {_fmt_count(stats.events)} events",
            font=_font(22),
            fill=FAINT,
        )
    return y + panel_h


def _layout_breakdowns(
    draw: ImageDraw.ImageDraw,
    overview: AgentypeOverview,
    y: int,
    *,
    do_draw: bool,
) -> int:
    for title, rows in _breakdown_groups(overview, limit=5):
        row_h = 44
        panel_h = 74 + len(rows) * row_h
        if do_draw:
            _panel(draw, y, panel_h)
            draw.text((PAD + 28, y + 28), f"> {title.lower()}", font=_font(26, bold=True), fill=CYAN)
            row_y = y + 76
            max_value = max([value for _, value in rows], default=1)
            for index, (name, value) in enumerate(rows):
                color = ROW_COLORS[index % len(ROW_COLORS)]
                draw.text((PAD + 28, row_y), _fit_text(name, 24), font=_font(23), fill=TEXT)
                draw.text((WIDTH - PAD - 140, row_y), _fmt_count(value), font=_font(22), fill=MUTED)
                _draw_single_bar(
                    draw,
                    PAD + 360,
                    row_y + 10,
                    CONTENT_WIDTH - 520,
                    value,
                    max_value,
                    color,
                    BAR_BG,
                    height=12,
                )
                row_y += row_h
        y += panel_h + 28
    return y


def _layout_usage_rhythm(
    draw: ImageDraw.ImageDraw,
    overview: AgentypeOverview,
    y: int,
    *,
    do_draw: bool,
) -> int:
    groups = _trend_groups(overview)
    row_h = 42
    panel_h = 78 + sum(42 + max(1, len(rows)) * row_h for _, rows in groups)
    if do_draw:
        _panel(draw, y, panel_h)
        draw.text((PAD + 28, y + 28), "3. Usage Rhythm", font=_font(27, bold=True), fill=GREEN)
        row_y = y + 84
        for title, rows in groups:
            values = [item.tokens_with_cache for item in rows]
            sparkline = _sparkline(values) if values else "-"
            draw.text((PAD + 28, row_y), f"{title} {sparkline}", font=_font(24, bold=True), fill=CYAN)
            row_y += 42
            if not rows:
                draw.text((PAD + 52, row_y), "-", font=_font(22), fill=FAINT)
                row_y += row_h
                continue
            max_value = max(values)
            for item in rows:
                _draw_period_bar(draw, item, max_value, row_y)
                row_y += row_h
    return y + panel_h


def _layout_footer(
    draw: ImageDraw.ImageDraw,
    generated_at: str,
    y: int,
    *,
    do_draw: bool,
    image: Image.Image | None = None,
) -> int:
    if do_draw:
        draw.text((PAD, y), f"generated {generated_at}", font=_font(22), fill=FAINT)
        draw.text((PAD, y + 34), "github.com/cyzlmh/agentype", font=_font(22), fill=CYAN)
        draw.text((PAD, y + 68), "scan for source, install docs, and marketplace links", font=_font(19), fill=MUTED)
        draw.text((PAD, y + 104), "agentype", font=_font(22, bold=True), fill=GREEN)
        if image is not None:
            qr = _github_qr()
            image.paste(qr, (WIDTH - PAD - QR_SIZE, y))
    return y + QR_SIZE


def _github_qr() -> Image.Image:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(GITHUB_URL)
    qr.make(fit=True)
    return qr.make_image(fill_color=BG, back_color=TEXT).convert("RGB")


def _panel(draw: ImageDraw.ImageDraw, y: int, height: int) -> None:
    draw.rounded_rectangle([PAD, y, WIDTH - PAD, y + height], radius=12, fill=PANEL)


def _breakdown_groups(overview: AgentypeOverview, *, limit: int) -> list[tuple[str, list[tuple[str, int]]]]:
    return [
        ("Projects", [(item.project, item.tokens_with_cache) for item in overview.statistics.projects[:limit]]),
        ("Agents", [(item.provider, item.tokens_with_cache) for item in overview.statistics.providers[:limit]]),
        (
            "Models",
            [
                (item.model, item.tokens_with_cache)
                for item in overview.statistics.models
                if item.model != "(unknown)"
            ][:limit],
        ),
    ]


def _trend_groups(overview: AgentypeOverview, *, limit: int = 8) -> list[tuple[str, list[PeriodStats]]]:
    return [
        ("Monthly", overview.statistics.monthly[-limit:]),
        ("Weekly", overview.statistics.weekly[-limit:]),
    ]


def _draw_period_bar(
    draw: ImageDraw.ImageDraw,
    item: PeriodStats,
    max_value: int,
    y: int,
) -> None:
    label = _fit_text(_display_period(item.period), 19)
    draw.text((PAD + 52, y), f"{label:<19}", font=_font(21), fill=TEXT)
    _draw_single_bar(
        draw,
        PAD + 360,
        y + 10,
        CONTENT_WIDTH - 520,
        item.tokens_with_cache,
        max_value,
        CYAN,
        BAR_BG,
        height=12,
    )
    draw.text((WIDTH - PAD - 140, y), _fmt_count(item.tokens_with_cache), font=_font(21), fill=MUTED)


def _draw_stacked_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    first: int,
    second: int,
    first_color: str,
    second_color: str,
    bg_color: str,
    *,
    height: int,
) -> None:
    total = first + second
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=bg_color)
    if total <= 0:
        return
    first_width = int(width * first / total)
    if first_width > 0:
        draw.rounded_rectangle([x, y, x + first_width, y + height], radius=height // 2, fill=first_color)
    if second > 0:
        draw.rounded_rectangle([x + first_width, y, x + width, y + height], radius=height // 2, fill=second_color)


def _draw_single_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    value: int,
    max_value: int,
    color: str,
    bg_color: str,
    *,
    height: int,
) -> None:
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=bg_color)
    filled = int(width * (value / max_value)) if max_value > 0 else 0
    if filled > 0:
        draw.rounded_rectangle([x, y, x + filled, y + height], radius=height // 2, fill=color)


def _sparkline(values: list[int]) -> str:
    if not values:
        return "-"
    levels = "▁▂▃▄▅▆▇█"
    high = max(values)
    low = min(values)
    if high == low:
        return levels[-1] * len(values)
    return "".join(levels[round((value - low) / (high - low) * (len(levels) - 1))] for value in values)


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


def render_card(
    archetype: str,
    persona_text: str,
    profile: dict,
    output_path: str | Path = "output/agentype.png",
) -> Path:
    """Backward-compatible terminal-style card renderer for older callers."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (WIDTH, LEGACY_HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    title = archetype or "Usage Snapshot"
    body = _clean_text(persona_text or "Local AI-agent usage summary.")

    draw.text((PAD, PAD), "$ agentype --png-out", font=_font(26), fill=FAINT)
    _draw_fitted_text(draw, title, PAD, PAD + 58, CONTENT_WIDTH, 62, GREEN, bold=True)
    _draw_wrapped_text(draw, body, PAD, PAD + 150, CONTENT_WIDTH, _font(30), TEXT, 42, 8)

    y = 560
    rows = [
        (name, int(score))
        for name, score in profile.get("domain_scores", {}).items()
    ][:6]
    if rows:
        _draw_legacy_rank_rows(draw, "breakdown", rows, y, max(row[1] for row in rows))

    footer_y = LEGACY_HEIGHT - PAD - QR_SIZE
    _layout_footer(draw, _generated_timestamp(), footer_y, do_draw=True, image=img)
    img.save(str(output_path), "PNG")
    return output_path


def _draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    max_size: int,
    fill: str,
    *,
    bold: bool = False,
) -> None:
    font = _fit_font(draw, text, max_width, max_size, 32, bold=bold)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    line_height: int,
    max_lines: int,
) -> None:
    lines = _wrap_lines(draw, text, font, max_width)[:max_lines]
    _draw_lines(draw, lines, x, y, font, fill, line_height)


def _draw_legacy_rank_rows(
    draw: ImageDraw.ImageDraw,
    title: str,
    rows: list[tuple[str, int]],
    y: int,
    max_value: int,
) -> None:
    draw.text((PAD, y), f"> {title}", font=_font(26, bold=True), fill=CYAN)
    row_y = y + 48
    for idx, (name, value) in enumerate(rows):
        color = ROW_COLORS[idx % len(ROW_COLORS)]
        draw.text((PAD, row_y), _fit_text(name, 24), font=_font(23), fill=TEXT)
        _draw_single_bar(draw, PAD + 280, row_y + 10, CONTENT_WIDTH - 340, value, max_value, color, BAR_BG, height=12)
        row_y += 42


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            lines.extend(textwrap.wrap(word, width=max(8, max_width // 18)))
            current = ""
    if current:
        lines.append(current)
    return lines


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    line_height: int,
) -> None:
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_size: int,
    min_size: int,
    *,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(max_size, min_size - 1, -2):
        font = _font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
    return _font(min_size, bold=bold)


def _text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _generated_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _clean_text(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return " ".join(text.split())


def _fit_text(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _fmt_count(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)
