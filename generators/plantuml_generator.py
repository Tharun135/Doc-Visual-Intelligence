"""
plantuml_generator.py

Deterministic, template-based PlantUML code generator.
No LLM involved — all output is derived from signals the rule engine
already extracted (step_lines, conditions, relationships).

This generator uses a centralized corporate theme (theme-documentation.puml)
to ensure consistent, professional styling across all diagram types.

Public API
----------
generate(visual_type, title, signals) -> str | None
    Returns valid PlantUML source (@startuml … @enduml) or None
    when the signals don't contain enough data to generate anything
    meaningful.

Individual generators are also exposed for direct use:
    generate_flowchart(title, steps)
    generate_sequence(title, steps)
    generate_decision(title, content)
    generate_component(title, signals)
"""

import base64
import logging
import os
import re
import subprocess
import tempfile
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)
PRIVACY_MODE = os.environ.get("DVI_PRIVACY_MODE", "1") == "1"
ALLOW_PLANTUML_API = os.environ.get("DVI_ALLOW_PLANTUML_API", "0") == "1"


# ─────────────────────────────────────────────
# Styling configuration
# ─────────────────────────────────────────────

class DiagramStyle:
    """Centralized styling configuration for all diagram types."""
    
    # Corporate theme — inline for PlantUML API compatibility
    # (public API cannot resolve !include directives)
    THEME_LINES = [
        "' Siemens documentation-diagram theme",
        'skinparam DefaultFontFamily "Segoe UI", "Roboto", sans-serif',
        "skinparam DefaultFontSize 14",
        "skinparam Shadowing false",
        "skinparam TitleFontSize 18",
        "skinparam TitleFontStyle bold",
        "skinparam TitleFontColor #FFFFFF",
        "skinparam activity {",
        "    BackgroundColor    #009999",
        "    BorderColor        #00646E",
        "    BorderThickness    3",
        "    FontColor          #FFFFFF",
        "    FontSize           15",
        "    Padding            20",
        "    Margin             14",
        "}",
        "skinparam activityDiamond {",
        "    BackgroundColor    #FFD732",
        "    BorderColor        #F7C600",
        "    BorderThickness    3",
        "    FontColor          #000028",
        "    FontSize           15",
        "}",
        "skinparam Arrow {",
        "    Color              #00646E",
        "    FontColor          #FFFFFF",
        "    FontSize           13",
        "    Thickness          4",
        "}",
        "skinparam activityStartColor #00FFB9",
        "skinparam activityEndColor #EF0137",
        "skinparam activityArrowColor #00646E",
        "skinparam ArrowThickness 4",
        "skinparam nodesep 70",
        "skinparam ranksep 90",
        "skinparam backgroundColor #000028",
    ]
    
    # Spacing and sizing
    COMPACT_THRESHOLD = 3      # steps → use compact spacing
    NORMAL_THRESHOLD = 8       # steps → use normal spacing
    LARGE_THRESHOLD = 15       # steps → use generous spacing
    
    # Text wrapping
    WRAP_LENGTH = 40           # wrap step labels at ~40 chars
    
    # Start/End nodes sizing
    START_END_SIZE = 2.0       # multiplier for start/end circle radius


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _sanitize(label: str) -> str:
    """Remove characters that confuse PlantUML node names."""
    label = re.sub(r"\s+", " ", label.strip()).strip(" -:;,.()[]{}")
    return label.replace('"', "'").replace("@", "at")


def _escape_plantuml_text(text: str) -> str:
    """Escape special characters for PlantUML activity diagram actions.
    
    PlantUML activity diagrams use :action; syntax where certain characters
    need escaping to avoid parsing errors. We use HTML entities for quotes
    which are reliably supported across PlantUML versions.
    """
    # Use HTML entity for single quote &#39; instead of escaping
    # This is more reliable across different PlantUML API versions
    text = text.replace("'", "&#39;")
    return text


def _wrap_text(text: str, max_chars: int = 40) -> str:
    """
    Wrap text at word boundaries to keep lines under max_chars.
    Joins lines with newlines for display in PlantUML boxes.
    
    Example:
        "Browse and select the project ZIP file generated"
        →
        "Browse and select the\nproject ZIP file generated"
    """
    words = text.split()
    lines = []
    current = []
    current_len = 0
    
    for word in words:
        word_len = len(word)
        # Account for spaces between words
        test_len = current_len + word_len + (1 if current else 0)
        
        if test_len > max_chars and current:
            # Start a new line
            lines.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len = test_len
    
    if current:
        lines.append(" ".join(current))
    
    return "\n".join(lines)


def _shorten(text: str, max_words: int = 7) -> str:
    """Keep the first few words of a step for compact node labels."""
    s = re.sub(r"^\s*(?:\d+[\.)]|step\s+\d+:?)\s*", "", text, flags=re.IGNORECASE)
    parts = re.split(r"\.|,|;|\(", s)
    short = parts[0].strip()
    words = short.split()
    if len(words) > max_words:
        short = " ".join(words[:max_words]) + "..."
    
    # Wrap the shortened version
    return _wrap_text(_sanitize(short), DiagramStyle.WRAP_LENGTH)


def _get_spacing_config(num_steps: int) -> dict:
    """Return spacing and sizing config based on procedure length."""
    if num_steps <= DiagramStyle.COMPACT_THRESHOLD:
        return {
            "top_margin": 8,
            "bottom_margin": 8,
            "line_height": 1.0,
            "scale": 0.9,
        }
    elif num_steps <= DiagramStyle.NORMAL_THRESHOLD:
        return {
            "top_margin": 12,
            "bottom_margin": 12,
            "line_height": 1.2,
            "scale": 1.0,
        }
    else:
        return {
            "top_margin": 16,
            "bottom_margin": 16,
            "line_height": 1.4,
            "scale": 1.1,
        }


# ─────────────────────────────────────────────
# Flowchart  (Activity diagram — professional)
# ─────────────────────────────────────────────

def generate_flowchart(title: str, steps: list[str]) -> str | None:
    """Generate a professional, modern activity diagram from steps."""
    if len(steps) < 2:
        return None
    
    spacing = _get_spacing_config(len(steps))
    
    lines = [
        "@startuml",
    ]
    lines.extend(DiagramStyle.THEME_LINES)
    lines.extend([
        "",
        f"title {_sanitize(title)}",
        "",
        "' Activity flow with professional styling",
        "start",
    ])
    
    for step in steps:
        wrapped = _wrap_text(_sanitize(step), DiagramStyle.WRAP_LENGTH)
        escaped = _escape_plantuml_text(wrapped)
        step_lower = step.lower()
        
        # Semantic shape mapping
        if any(w in step_lower for w in ("verify", "check status", "validate", "confirm")):
            # Verification steps as decision diamonds
            lines.append(f'if ({escaped}?) then (yes)')
            lines.append("  :Continue;")
            lines.append("else (no)")
            lines.append("  :Troubleshoot;")
            lines.append("endif")
        else:
            # Normal activity
            lines.append(f':{escaped};')
    
    lines += [
        "stop",
        "",
        "@enduml",
    ]
    
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Sequence diagram (professional)
# ─────────────────────────────────────────────

_ACTOR_HINTS = {
    "user": "User",
    "browser": "Browser",
    "client": "Client",
    "server": "Server",
    "gateway": "Gateway",
    "plc": "PLC",
    "hmi": "HMI",
    "cloud": "Cloud",
    "databus": "Databus",
    "connector": "Connector",
    "ie hub": "IE Hub",
    "edge device": "Edge Device",
    "insights hub": "Insights Hub",
    "mindsphere": "MindSphere",
}


def _extract_actors(steps: list[str]) -> list[str]:
    """Heuristic: detect named actors from step text, or fall back to two generics."""
    found = []
    combined = " ".join(steps).lower()
    for keyword, label in _ACTOR_HINTS.items():
        if keyword in combined and label not in found:
            found.append(label)
        if len(found) >= 3:
            break
    if len(found) < 2:
        found = ["System", "Component"]
    return found[:3]


def generate_sequence(title: str, steps: list[str]) -> str | None:
    """Generate a professional sequence diagram."""
    if len(steps) < 2:
        return None

    actors = _extract_actors(steps)
    
    lines = [
        "@startuml",
    ]
    lines.extend(DiagramStyle.THEME_LINES)
    lines.extend([
        "",
        f"title {_sanitize(title)}",
        "",
        "' Sequence diagram showing component interactions",
    ])
    
    for actor in actors:
        lines.append(f'participant "{actor}"')
    
    lines.append("")
    src = actors[0]
    dst = actors[1]
    alt = actors[2] if len(actors) > 2 else dst

    for i, step in enumerate(steps):
        wrapped = _wrap_text(_sanitize(step), 50)
        # Alternate message direction for visual variety
        if i % 3 == 2 and len(actors) > 2:
            lines.append(f'"{src}" -> "{alt}" : {wrapped}')
        elif i % 2 == 0:
            lines.append(f'"{src}" -> "{dst}" : {wrapped}')
        else:
            lines.append(f'"{dst}" --> "{src}" : {wrapped}')

    lines += ["", "@enduml"]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Decision tree (professional)
# ─────────────────────────────────────────────

def _extract_conditions(content: str) -> list[tuple[str, str, str]]:
    """Extract condition/action pairs from prose."""
    results = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", content)
    for sentence in sentences:
        sentence = sentence.strip()
        m = re.search(r"\b[Ii]f\b\s+(.+?)(?:,|\sthen\s)\s*(.+)", sentence)
        if m:
            cond = _wrap_text(_sanitize(m.group(1).strip()), 35)
            yes_act = _wrap_text(_sanitize(m.group(2).strip(" .")), 35)
            else_m = re.search(
                r"\b(otherwise|else|if not)\b[,\s]+(.+)",
                sentence,
                re.IGNORECASE,
            )
            no_act = (
                _wrap_text(_sanitize(else_m.group(2).strip(" .")), 35)
                if else_m
                else "Continue"
            )
            if cond and yes_act:
                results.append((cond, yes_act, no_act))
    return results[:4]


def generate_decision(title: str, content: str) -> str | None:
    """Generate a professional decision-tree activity diagram."""
    conditions = _extract_conditions(content)
    if not conditions:
        return None

    lines = [
        "@startuml",
    ]
    lines.extend(DiagramStyle.THEME_LINES)
    lines.extend([
        "",
        f"title {_sanitize(title)}",
        "",
        "' Decision tree showing conditional branches",
        "start",
    ])

    for cond, yes_act, no_act in conditions:
        lines.append(f"if ({cond}?) then (yes)")
        lines.append(f"  :{yes_act};")
        lines.append(f"else (no)")
        lines.append(f"  :{no_act};")
        lines.append("endif")

    lines += ["stop", "", "@enduml"]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Architecture / Topology / Data Flow (professional)
# ─────────────────────────────────────────────

_COMPONENT_KEYWORDS = [
    "plc", "hmi", "server", "gateway", "connector", "edge device", "ie hub",
    "industrial edge", "cloud", "mqtt", "opc ua", "opcua", "s7", "simatic",
    "insights hub", "mindsphere", "databus", "ie databus", "browser", "client",
    "database", "api", "service",
]

_RELATION_RE = re.compile(
    r"(?P<src>.+?)\s+"
    r"(?:sends|transfers|forwards|publishes|subscribes|routes|connects\s+to|communicates\s+with|→|->)\s+"
    r"(?:.+?\s+to\s+)?(?P<dst>[A-Za-z][\w\s]{2,30})",
    re.IGNORECASE,
)


def _extract_components(content: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Extract component names and relationship pairs from prose."""
    content_lower = content.lower()

    found_components: list[str] = []
    for kw in _COMPONENT_KEYWORDS:
        if kw in content_lower:
            label = " ".join(w.capitalize() for w in kw.split())
            if label not in found_components:
                found_components.append(label)

    relations: list[tuple[str, str]] = []
    for line in content.splitlines():
        m = _RELATION_RE.search(line)
        if m:
            src = _sanitize(m.group("src").strip())[:30]
            dst = _sanitize(m.group("dst").strip())[:30]
            if src and dst and src.lower() != dst.lower():
                relations.append((src, dst))

    return found_components[:8], relations[:10]


def generate_component(title: str, signals: dict, content: str = "") -> str | None:
    """Generate a professional component/architecture diagram."""
    components, relations = _extract_components(content)

    if not components and not relations:
        return None

    lines = [
        "@startuml",
    ]
    lines.extend(DiagramStyle.THEME_LINES)
    lines.extend([
        "",
        f"title {_sanitize(title)}",
        "",
        "' Component architecture with clear connections",
        "",
    ])

    # Declare all detected components
    declared: set[str] = set()
    for comp in components:
        safe = re.sub(r"\W+", "_", comp)
        lines.append(f'component "{comp}" as {safe}')
        declared.add(comp.lower())

    # Add any relationship endpoints not yet declared
    for src, dst in relations:
        for name in (src, dst):
            if name.lower() not in declared:
                safe = re.sub(r"\W+", "_", name)
                lines.append(f'component "{name}" as {safe}')
                declared.add(name.lower())

    if relations:
        lines.append("")
        for src, dst in relations:
            src_safe = re.sub(r"\W+", "_", src)
            dst_safe = re.sub(r"\W+", "_", dst)
            lines.append(f"{src_safe} --> {dst_safe}")
    elif len(components) >= 2:
        lines.append("")
        for i in range(len(components) - 1):
            s = re.sub(r"\W+", "_", components[i])
            d = re.sub(r"\W+", "_", components[i + 1])
            lines.append(f"{s} --> {d}")

    lines += ["", "@enduml"]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Public dispatcher
# ─────────────────────────────────────────────

def generate(visual_type: str, title: str, signals: dict, content: str = "") -> str | None:
    """
    Generate professional PlantUML source for the given visual type.

    Parameters
    ----------
    visual_type : str
        One of the types emitted by detect_visuals().
    title : str
        Section title — used as the diagram title.
    signals : dict
        Signal dict from compute_signals().
    content : str
        Raw section text — needed for decision/component diagrams.

    Returns
    -------
    str | None
        Valid PlantUML source, or None if insufficient data.
    """
    steps = signals.get("step_lines", [])

    if visual_type in ("Workflow Diagram", "Flowchart"):
        return generate_flowchart(title, steps)

    if visual_type == "Sequence Diagram":
        return generate_sequence(title, steps)

    if visual_type == "Decision Tree":
        return generate_decision(title, content)

    if visual_type in ("Architecture Diagram", "Topology Diagram", "Data Flow Diagram"):
        return generate_component(title, signals, content)

    return None


# ─────────────────────────────────────────────
# PlantUML rendering (JAR + public API fallback)
# Moved here from mcp/plantuml_server.py so the
# app has no MCP dependency.
# ─────────────────────────────────────────────

_PLANTUML_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _encode_6bit(b: int) -> str:
    return _PLANTUML_CHARS[b & 0x3F]


def _append_3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return _encode_6bit(c1) + _encode_6bit(c2) + _encode_6bit(c3) + _encode_6bit(c4)


def _plantuml_encode(source: str) -> str:
    """Encode PlantUML source for use in the public REST API URL."""
    data = zlib.compress(source.encode("utf-8"), 9)[2:-4]
    result = []
    i = 0
    while i < len(data):
        b1 = data[i]
        b2 = data[i + 1] if i + 1 < len(data) else 0
        b3 = data[i + 2] if i + 2 < len(data) else 0
        result.append(_append_3bytes(b1, b2, b3))
        i += 3
    return "".join(result)


def _render_via_jar(code: str, jar_path: Path) -> tuple[str | None, str | None]:
    """Render PlantUML code using a local JAR file. Returns (svg_str, error)."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "diagram.puml"
            src_file.write_text(code, encoding="utf-8")
            result = subprocess.run(
                ["java", "-jar", str(jar_path), "-tsvg", "-charset", "UTF-8", str(src_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return None, f"PlantUML JAR error: {result.stderr.strip()}"
            svg_file = Path(tmpdir) / "diagram.svg"
            if svg_file.exists():
                return svg_file.read_text(encoding="utf-8"), None
            return None, "PlantUML JAR ran but produced no SVG file."
    except FileNotFoundError:
        return None, "java is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return None, "PlantUML JAR timed out after 30 seconds."
    except Exception as exc:
        return None, f"Unexpected error running PlantUML JAR: {exc}"


def _render_via_api(code: str) -> tuple[str | None, str | None]:
    """Render PlantUML code via the public plantuml.com API. Returns (svg_str, error)."""
    try:
        import urllib.request
        encoded = _plantuml_encode(code)
        url = f"https://www.plantuml.com/plantuml/svg/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Doc-Visual-Intelligence/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            svg = response.read().decode("utf-8")
        if "<svg" not in svg:
            return None, f"PlantUML API returned unexpected content: {svg[:200]}"
        return svg, None
    except Exception as exc:
        return None, f"PlantUML API request failed: {exc}"


def render_plantuml(code: str) -> tuple[str | None, str | None]:
    """
    Render PlantUML source code to SVG.

    Tries a local JAR first (PLANTUML_JAR env var or plantuml.jar in the
    project root). Public API fallback is disabled in privacy mode unless
    DVI_ALLOW_PLANTUML_API=1 is explicitly set.

    Returns
    -------
    (svg, error) : tuple[str | None, str | None]
        On success: (svg_string, None)
        On failure: (None, error_message)
    """
    if not code or not code.strip():
        return None, "Empty PlantUML code provided."

    jar_env = os.environ.get("PLANTUML_JAR", "")
    project_jar = Path(__file__).parent.parent / "plantuml.jar"

    if jar_env and Path(jar_env).is_file():
        logger.info("Rendering via local JAR: %s", jar_env)
        svg, err = _render_via_jar(code, Path(jar_env))
        if svg:
            return svg, None
        logger.warning("JAR render failed (%s), falling back to API.", err)
    elif project_jar.is_file():
        logger.info("Rendering via project JAR: %s", project_jar)
        svg, err = _render_via_jar(code, project_jar)
        if svg:
            return svg, None
        logger.warning("JAR render failed (%s), falling back to API.", err)

    if PRIVACY_MODE and not ALLOW_PLANTUML_API:
        return None, "PlantUML rendering requires a local plantuml.jar in privacy mode. Public API fallback is disabled."

    if not ALLOW_PLANTUML_API:
        return None, "PlantUML API fallback is disabled. Set DVI_ALLOW_PLANTUML_API=1 to enable remote rendering."

    logger.info("Rendering via PlantUML public API.")
    return _render_via_api(code)

