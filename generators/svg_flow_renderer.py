"""Native SVG renderer for simple linear documentation workflows."""
# Trigger reload

from functools import lru_cache
from html import escape
import json
from pathlib import Path
import re
import textwrap

_CANVAS_WIDTH = 980
_MIN_CARD_WIDTH = 300
_CARD_HEIGHT = 120
_TOP_MARGIN = 48
_BOTTOM_MARGIN = 48
_LEFT_PAD = 28


@lru_cache(maxsize=1)
def _load_theme() -> dict:
    """Load Siemens theme configuration with safe defaults."""
    defaults = {
        "background": "#000028",
        "title": "#FFFFFF",
        "subtitle": "#A6F7E5",
        "activityFill": "#009999",
        "activityBorder": "#00646E",
        "activityText": "#FFFFFF",
        "systemFill": "#009999",
        "systemBorder": "#00646E",
        "systemText": "#FFFFFF",
        "validationFill": "#FFD732",
        "validationBorder": "#F7C600",
        "validationText": "#000028",
        "warningFill": "#FFD732",
        "warningBorder": "#F7C600",
        "warningText": "#000028",
        "outputFill": "#00FFB9",
        "outputBorder": "#00CFA0",
        "outputText": "#000028",
        "resultFill": "#6FEFD3",
        "resultBorder": "#00CFA0",
        "resultText": "#000028",
        "connector": "#00646E",
        "numberFill": "#000028",
        "numberBorder": "#009999",
        "numberText": "#FFFFFF",
        "metricsBorder": "#00646E",
        "metricsText": "#FFFFFF",
        "fontFamily": "Segoe UI, Roboto, sans-serif",
        "titleSize": 24,
        "subtitleSize": 13,
        "cardLabelSize": 13,
        "cardTextSize": 16,
        "numberSize": 17,
        "cardRadius": 16,
        "cardPaddingY": 36,
        "stepGap": 106,
        "errorFill": "#EF0137",
        "errorBorder": "#D50033",
        "errorText": "#FFFFFF",
        "successFill": "#00FFB9",
        "successBorder": "#00CFA0",
        "successText": "#000028",
        "warningFill": "#FF9900",
        "warningBorder": "#E67E00",
        "warningText": "#000028",
    }

    theme_path = Path(__file__).with_name("siemens_theme.json")
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            defaults.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass

    return defaults


def _sanitize_step(step: str) -> str:
    s = re.sub(r"^\s*(?:\d+[\.)]|step\s+\d+\s*:?)+\s*", "", step, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" -:;,.()[]{}")
    return s.strip()


def _shorten(text: str, max_words: int = 15) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _step_kind(step: str) -> tuple[str, str, str]:
    lower = step.lower()

    # Error/failure detection (highest priority)
    if any(k in lower for k in ("error", "fail", "failed", "failure", "exception", "abort", "stop", "cannot", "unable")):
        return ("error", "❌", "ERROR")

    # Success/completion detection
    if any(k in lower for k in ("success", "successful", "complete", "completed", "done", "finished", "passed", "confirmed", "verified")):
        return ("success", "✔", "SUCCESS")

    # Output/result generation
    if any(k in lower for k in ("created", "available", "saved", "generated", "produce", "generates", "create", "result", "output", "appears", "ready")):
        return ("output", "📄", "OUTPUT")

    # Validation/checking (lower priority than errors/success)
    if any(k in lower for k in ("verify", "validate", "validation", "check status", "confirm", "inspect", "review", "examine")):
        return ("validation", "✓", "VALIDATION")

    # Warning conditions
    if any(k in lower for k in ("warning", "caution", "attention", "important", "must", "required", "ensure")):
        return ("warning", "⚠", "WARNING")

    # System/async operations
    if any(k in lower for k in ("wait", "delay", "pause", "processing", "running", "in progress", "loading", "waiting", "execute", "run")):
        return ("system", "⏳", "SYSTEM")

    # Result/view operations
    if any(k in lower for k in ("view", "open", "display", "show", "see", "browse", "navigate")):
        return ("output", "📂", "RESULT")

    if any(k in lower for k in ("click", "select", "choose", "enter", "type", "navigate", "browse", "upload", "download")):
        return ("user", "🖱", "USER")

    return ("system", "⚙", "SYSTEM")


def _card_style(kind: str, theme: dict) -> tuple[str, str, str]:
    # Flat fills without glow to stay aligned with Siemens documentation styling.
    if kind == "user":
        return (theme["activityFill"], theme["activityBorder"], theme["activityText"])
    if kind == "system":
        return (theme["systemFill"], theme["systemBorder"], theme["systemText"])
    if kind == "error":
        return (theme["errorFill"], theme["errorBorder"], theme["errorText"])
    if kind == "success":
        return (theme["successFill"], theme["successBorder"], theme["successText"])
    if kind == "warning":
        return (theme["warningFill"], theme["warningBorder"], theme["warningText"])
    if kind == "validation":
        return (theme["validationFill"], theme["validationBorder"], theme["validationText"])
    if kind == "output":
        return (theme["outputFill"], theme["outputBorder"], theme["outputText"])
    if kind == "result":
        return (theme["resultFill"], theme["resultBorder"], theme["resultText"])
    return (theme["activityFill"], theme["activityBorder"], theme["activityText"])


def generate_simple_flow_svg(title: str, steps: list[str], signals: dict | None = None) -> str | None:
    if len(steps) < 2:
        return None

    theme = _load_theme()

    clean_steps = [_shorten(_sanitize_step(s)) for s in steps if _sanitize_step(s)]
    if len(clean_steps) < 2:
        return None

    # Adaptive font sizing: larger fonts for shorter workflows
    step_count = len(clean_steps)
    is_short = step_count <= 6
    is_very_short = step_count <= 4
    title_size_override = int(theme.get("titleSize", 36)) + (8 if is_very_short else 6 if is_short else 0)
    card_text_size_override = int(theme.get("cardTextSize", 22)) + (6 if is_very_short else 4 if is_short else 0)
    card_label_size_override = int(theme.get("cardLabelSize", 16)) + (3 if is_very_short else 2 if is_short else 0)
    number_size_override = int(theme.get("numberSize", 22)) + (3 if is_short else 0)

    wrapped_steps = []
    max_line_chars = 0
    for step in clean_steps:
        kind, icon, label = _step_kind(step)
        lines = textwrap.wrap(step, width=38)[:3]
        if len(textwrap.wrap(step, width=38)) > 3:
             lines[2] = lines[2] + "..."
        wrapped_steps.append((kind, icon, label, lines))
        for line in lines:
            if len(line) > max_line_chars:
                max_line_chars = len(line)

    _DYNAMIC_CARD_HEIGHT = 150
    card_width = max(_MIN_CARD_WIDTH, 140 + max_line_chars * 15)
    canvas_width = card_width + 60

    card_x = (canvas_width - card_width) // 2
    number_x = card_x + 32
    text_center_x = card_x + 68 + (card_width - 68) // 2

    total_steps = len(clean_steps)
    step_gap = int(theme.get("stepGap", 80))
    canvas_height = _TOP_MARGIN + total_steps * _DYNAMIC_CARD_HEIGHT + (total_steps - 1) * step_gap + _BOTTOM_MARGIN

    card_radius = int(theme.get("cardRadius", 16))
    title_size = title_size_override
    subtitle_size = int(theme.get("subtitleSize", 13))
    card_label_size = card_label_size_override
    card_text_size = card_text_size_override
    number_size = number_size_override
    font_family = theme.get("fontFamily", "Segoe UI, Roboto, sans-serif")
    connector = theme["connector"]

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="{escape(title)} flow diagram">')
    parts.append("  <defs>")
    parts.append("    <style>")
    parts.append("      @keyframes flowAnim {")
    parts.append("        from { stroke-dashoffset: 14; }")
    parts.append("        to { stroke-dashoffset: 0; }")
    parts.append("      }")
    parts.append("      .flow-line {")
    parts.append("        animation: flowAnim 0.8s linear infinite;")
    parts.append("      }")
    parts.append("    </style>")
    import uuid
    marker_id = f"stepArrow_{uuid.uuid4().hex[:8]}"
    parts.append(f"    <marker id=\"{marker_id}\" markerWidth=\"24\" markerHeight=\"24\" refX=\"18\" refY=\"12\" orient=\"auto\" markerUnits=\"userSpaceOnUse\">")
    parts.append(f'      <path d="M0,4 L18,12 L0,20 z" fill="{connector}"/>')
    parts.append("    </marker>")
    parts.append("  </defs>")

    parts.append(f'  <rect width="{canvas_width}" height="{canvas_height}" fill="{theme["background"]}" rx="20" ry="20"/>')

    for index, item in enumerate(wrapped_steps, start=1):
        kind, icon, label, lines = item
        fill, stroke, text_color = _card_style(kind, theme)
        y = _TOP_MARGIN + (index - 1) * (_DYNAMIC_CARD_HEIGHT + step_gap)
        cy = y + _DYNAMIC_CARD_HEIGHT // 2

        # Connector to next node
        if index < total_steps:
            next_y = _TOP_MARGIN + index * (_DYNAMIC_CARD_HEIGHT + step_gap)
            line_start = y + _DYNAMIC_CARD_HEIGHT + 12
            line_end = next_y - 12
            parts.append(
                f'  <line class="flow-line" x1="{canvas_width // 2}" y1="{line_start}" x2="{canvas_width // 2}" y2="{line_end}" stroke="{connector}" stroke-width="3.2" stroke-dasharray="6 8" opacity="0.96" marker-end="url(#{marker_id})"/>'
            )

        # Card background
        parts.append(
            f'  <rect x="{card_x}" y="{y}" width="{card_width}" height="{_DYNAMIC_CARD_HEIGHT}" rx="{card_radius}" ry="{card_radius}" fill="{fill}" stroke="{stroke}" stroke-width="2.8"/>'
        )

        # Embedded step number (inside box left edge) - drawn ON TOP of rect
        parts.append(
            f'  <circle cx="{number_x}" cy="{cy}" r="18" fill="{theme["numberFill"]}" stroke="{theme["numberBorder"]}" stroke-width="2.4"/>'
        )
        parts.append(
            f'  <text x="{number_x}" y="{cy + 6}" text-anchor="middle" fill="{theme["numberText"]}" font-size="{number_size}" font-family="{font_family}" font-weight="700">{index}</text>'
        )
        if len(lines) == 1:
            parts.append(f'  <text x="{text_center_x}" y="{y + 80}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[0])}</text>')
        elif len(lines) == 2:
            parts.append(f'  <text x="{text_center_x}" y="{y + 66}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[0])}</text>')
            parts.append(f'  <text x="{text_center_x}" y="{y + 94}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[1])}</text>')
        else:
            parts.append(f'  <text x="{text_center_x}" y="{y + 52}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[0])}</text>')
            parts.append(f'  <text x="{text_center_x}" y="{y + 80}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[1])}</text>')
            parts.append(f'  <text x="{text_center_x}" y="{y + 108}" text-anchor="middle" fill="{text_color}" font-size="{card_text_size}" font-family="{font_family}" font-weight="600">{escape(lines[2])}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
