"""SVG renderer for architecture diagrams with semantic containers and legend."""

from functools import lru_cache
from html import escape
import json
import math
from pathlib import Path
from typing import Optional


@lru_cache(maxsize=1)
def _load_theme() -> dict:
    defaults = {
        "background": "#000028",
        "title": "#FFFFFF",
        "subtitle": "#A6F7E5",
        "fontFamily": "Segoe UI, Roboto, sans-serif",
        "cloud": {"fill": "#9C27B0", "border": "#7B1FA2", "text": "#FFFFFF"},
        "server": {"fill": "#1976D2", "border": "#1565C0", "text": "#FFFFFF"},
        "gateway": {"fill": "#0288D1", "border": "#0277BD", "text": "#FFFFFF"},
        "network_component": {"fill": "#0288D1", "border": "#0277BD", "text": "#FFFFFF"},
        "database": {"fill": "#616161", "border": "#424242", "text": "#FFFFFF"},
        "device": {"fill": "#4CAF50", "border": "#388E3C", "text": "#FFFFFF"},
        "runtime": {"fill": "#009999", "border": "#00646E", "text": "#FFFFFF"},
        "application": {"fill": "#009999", "border": "#00646E", "text": "#FFFFFF"},
        "interface": {"fill": "#FF6F00", "border": "#E65100", "text": "#FFFFFF"},
        "system": {"fill": "#1976D2", "border": "#1565C0", "text": "#FFFFFF"},
        "external_system": {"fill": "#9C27B0", "border": "#7B1FA2", "text": "#FFFFFF"},
        "connector": "#00B8A9",
        "connectorLabel": "#FFFFFF",
        "containerFill": "#0A2140",
        "containerStroke": "#4FC3F7",
        "containerTitle": "#D7F6FF",
        "legendText": "#FFFFFF",
        "titleSize": 34,
        "subtitleSize": 14,
        "nodeRadius": 10,
        "nodeLabelSize": 16,
        "connectionLabelSize": 14,
    }

    theme_path = Path(__file__).with_name("siemens_theme.json")
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            defaults.update({k: v for k, v in loaded.items() if not k.startswith("_")})
    except (OSError, json.JSONDecodeError):
        pass

    return defaults


def _compute_line_intersection(x1: float, y1: float, x2: float, y2: float, box_w: float, box_h: float) -> tuple[float, float]:
    """Approximate line-box boundary intersection for connector anchors."""
    if x1 == x2 and y1 == y2:
        return x2, y2

    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-6:
        return x2, y2 - (box_h / 2 if dy > 0 else -box_h / 2)

    slope = dy / dx
    half_w = box_w / 2
    half_h = box_h / 2

    x_sign = 1 if dx > 0 else -1
    y_at_w = slope * (half_w * x_sign)
    if abs(y_at_w) <= half_h:
        return x2 - half_w * x_sign, y2 - y_at_w

    y_sign = 1 if dy > 0 else -1
    x_at_h = (half_h * y_sign) / slope if abs(slope) > 1e-6 else 0
    return x2 - x_at_h, y2 - half_h * y_sign


def _node_colors(node_type: str, theme: dict) -> tuple[str, str, str]:
    colors = theme.get(node_type, theme.get("application", {}))
    if isinstance(colors, dict):
        return colors.get("fill", "#009999"), colors.get("border", "#00646E"), colors.get("text", "#FFFFFF")
    return "#009999", "#00646E", "#FFFFFF"


def _split_label(label: str, max_len: int = 18) -> list[str]:
    words = label.split()
    if not words:
        return [label]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        if len(test) <= max_len:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:2]


def _extract_layout(positions: dict, fallback_width: int, fallback_height: int) -> tuple[dict, dict, list[dict], set[str], int, int, list[dict]]:
    if positions and isinstance(positions, dict) and "positions" in positions:
        layout = positions
        pos = layout.get("positions", {})
        node_sizes = layout.get("node_sizes", {})
        containers = layout.get("containers", [])
        hidden_nodes = set(layout.get("hidden_nodes", []))
        canvas = layout.get("canvas", {})
        edges = layout.get("edges", [])
        width = int(canvas.get("width", fallback_width))
        height = int(canvas.get("height", fallback_height))
        return pos, node_sizes, containers, hidden_nodes, width, height, edges

    return positions or {}, {}, [], set(), fallback_width, fallback_height, []


def generate_architecture_svg(title: str, nodes: list[dict], edges: list[dict], positions: dict, width: int = 1280, height: int = 920, pattern=None) -> Optional[str]:
    if not nodes or len(nodes) < 2 or not edges:
        return None

    theme = _load_theme()
    pos, node_sizes, containers, hidden_nodes, canvas_w, canvas_h, layout_edges = _extract_layout(positions, width, height)
    edge_list = layout_edges if layout_edges else edges

    node_by_id = {node["id"]: node for node in nodes}

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-label="{escape(title)} architecture diagram">')
    parts.append("  <defs>")
    parts.append('    <marker id="arrowhead" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto">')
    parts.append(f'      <polygon points="0 0, 12 4, 0 8" fill="{theme["connector"]}"/>')
    parts.append("    </marker>")
    parts.append("  </defs>")

    parts.append(f'  <rect width="{canvas_w}" height="{canvas_h}" fill="{theme["background"]}" rx="22" ry="22"/>')

    parts.append("  <g>")
    parts.append(
        f'    <text x="{canvas_w // 2}" y="56" text-anchor="middle" fill="{theme["title"]}" font-size="{theme["titleSize"]}" font-weight="700" font-family="{theme["fontFamily"]}">{escape(title)}</text>'
    )
    
    # Add pattern detection metadata as subtitle
    if pattern and pattern.pattern.value != "generic":
        pattern_name = pattern.pattern.value.replace("_", " ").title()
        pattern_text = f"Pattern: {pattern_name} (confidence: {pattern.confidence:.0%})"
        parts.append(
            f'    <text x="{canvas_w // 2}" y="96" text-anchor="middle" fill="{theme["subtitle"]}" font-size="14" font-family="{theme["fontFamily"]}">{escape(pattern_text)}</text>'
        )
    
    parts.append(
        f'    <line x1="{canvas_w // 2 - 280}" y1="78" x2="{canvas_w // 2 + 280}" y2="78" stroke="{theme["cloud"].get("fill", "#9C27B0")}" stroke-width="2.4" opacity="0.85"/>'
    )
    parts.append("  </g>")

    # Containers first.
    for container in containers:
        x = container.get("x", 0)
        y = container.get("y", 0)
        w = container.get("width", 200)
        h = container.get("height", 160)
        header_h = container.get("header_height", 42)
        label = container.get("label", "Container")
        parts.append(
            f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" ry="16" fill="{theme["containerFill"]}" stroke="{theme["containerStroke"]}" stroke-width="2.2" opacity="0.92"/>'
        )
        parts.append(
            f'  <line x1="{x}" y1="{y + header_h}" x2="{x + w}" y2="{y + header_h}" stroke="{theme["containerStroke"]}" stroke-width="1.6" opacity="0.8"/>'
        )
        parts.append(
            f'  <text x="{x + w / 2}" y="{y + 28}" text-anchor="middle" fill="{theme["containerTitle"]}" font-size="15" font-family="{theme["fontFamily"]}" font-weight="700">{escape(label)}</text>'
        )

    # Draw connectors.
    for edge in edge_list:
        source_id = edge.get("source")
        target_id = edge.get("target")
        if source_id not in pos or target_id not in pos:
            continue
        if source_id not in node_by_id or target_id not in node_by_id:
            continue

        sx, sy = pos[source_id]
        tx, ty = pos[target_id]
        source_w, source_h = node_sizes.get(source_id, (220, 96))
        target_w, target_h = node_sizes.get(target_id, (220, 96))

        start_x, start_y = _compute_line_intersection(tx, ty, sx, sy, source_w, source_h)
        end_x, end_y = _compute_line_intersection(sx, sy, tx, ty, target_w, target_h)

        edge_type = edge.get("type", "connects")
        dashed = edge_type in {"connects", "communicates"}
        dash_style = ' stroke-dasharray="6 6"' if dashed else ""

        parts.append(
            f'  <line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" stroke="{theme["connector"]}" stroke-width="3" opacity="0.95"{dash_style} marker-end="url(#arrowhead)"/>'
        )

        label = edge.get("protocol") or edge.get("label") or ""
        if label:
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2
            label_width = max(86, min(220, 26 + len(label) * 9))
            label_height = 28
            parts.append(
                f'  <rect x="{mid_x - label_width / 2}" y="{mid_y - label_height / 2}" width="{label_width}" height="{label_height}" rx="6" fill="{theme["background"]}" stroke="{theme["connector"]}" stroke-width="1.4" opacity="0.97"/>'
            )
            parts.append(
                f'  <text x="{mid_x}" y="{mid_y + 5}" text-anchor="middle" fill="{theme["connectorLabel"]}" font-size="{theme["connectionLabelSize"]}" font-family="{theme["fontFamily"]}" font-weight="700">{escape(label)}</text>'
            )

    # Draw visible nodes.
    node_radius = theme.get("nodeRadius", 10)
    label_size = theme.get("nodeLabelSize", 16)

    for node in nodes:
        node_id = node["id"]
        if node_id in hidden_nodes or node_id not in pos:
            continue

        x, y = pos[node_id]
        w, h = node_sizes.get(node_id, (220, 96))
        node_type = node.get("type", "application")
        name = node.get("name", node_id)
        fill, border, text_color = _node_colors(node_type, theme)

        rect_x = x - w / 2
        rect_y = y - h / 2

        parts.append(
            f'  <rect x="{rect_x}" y="{rect_y}" width="{w}" height="{h}" rx="{node_radius}" ry="{node_radius}" fill="{fill}" stroke="{border}" stroke-width="2.8"/>'
        )

        lines = _split_label(name)
        if len(lines) == 1:
            parts.append(
                f'  <text x="{x}" y="{y + 6}" text-anchor="middle" fill="{text_color}" font-size="{label_size}" font-family="{theme["fontFamily"]}" font-weight="700">{escape(lines[0])}</text>'
            )
        else:
            parts.append(
                f'  <text x="{x}" y="{y - 4}" text-anchor="middle" fill="{text_color}" font-size="{label_size - 1}" font-family="{theme["fontFamily"]}" font-weight="700">{escape(lines[0])}</text>'
            )
            parts.append(
                f'  <text x="{x}" y="{y + 18}" text-anchor="middle" fill="{text_color}" font-size="{label_size - 1}" font-family="{theme["fontFamily"]}" font-weight="700">{escape(lines[1])}</text>'
            )

    # Legend to explain color meaning.
    legend_entries = [
        ("cloud", "Cloud Service"),
        ("gateway", "Gateway"),
        ("application", "Application"),
        ("device", "Device"),
        ("database", "Database"),
    ]
    legend_x = canvas_w - 310
    legend_y = canvas_h - 118
    parts.append(f'  <rect x="{legend_x}" y="{legend_y}" width="280" height="92" rx="10" fill="#0A1938" stroke="#355C7D" stroke-width="1.6" opacity="0.95"/>')
    parts.append(f'  <text x="{legend_x + 16}" y="{legend_y + 20}" fill="{theme["legendText"]}" font-size="13" font-family="{theme["fontFamily"]}" font-weight="700">Legend</text>')

    row_y = legend_y + 40
    col_split = legend_x + 138
    for idx, (type_name, display_name) in enumerate(legend_entries):
        col_x = legend_x + 14 if idx < 3 else col_split
        y = row_y + (idx % 3) * 20
        fill, border, _ = _node_colors(type_name, theme)
        parts.append(f'  <rect x="{col_x}" y="{y - 10}" width="14" height="14" rx="3" fill="{fill}" stroke="{border}" stroke-width="1"/>')
        parts.append(f'  <text x="{col_x + 22}" y="{y + 1}" fill="{theme["legendText"]}" font-size="12" font-family="{theme["fontFamily"]}">{display_name}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
