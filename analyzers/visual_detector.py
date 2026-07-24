"""
visual_detector.py — v2

Detection strategy:
1. compute_signals()  — extract structural patterns from content
2. Python rules       — reader-task pattern matching (rule_definitions.py)
3. JSON rules         — simple keyword overrides (visual_rules.json)
4. merge + rank       — deduplicate, score visual worthiness, return top 3
"""

import json
import re
import logging
from pathlib import Path

from rules.rule_definitions import PYTHON_RULES, Rule, RuleResult
from generators.plantuml_generator import generate as generate_plantuml
from generators.svg_flow_renderer import generate_simple_flow_svg
from generators.architecture_orchestrator import generate_architecture_diagram
from generators.screenshot_specification import generate_screenshot_specification

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Rule file loading (with error handling)
# ─────────────────────────────────────────────

_RULES_PATH = Path(__file__).parent.parent / "rules" / "visual_rules.json"
_KNOWLEDGE_PATH = Path(__file__).parent.parent / "rules" / "knowledge_model.json"


def _load_json(path: Path, label: str) -> list | dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("%s not found at %s — using empty fallback", label, path)
        return [] if label != "knowledge_model" else {}
    except json.JSONDecodeError as exc:
        logger.error("Malformed %s: %s — using empty fallback", label, exc)
        return [] if label != "knowledge_model" else {}


JSON_RULES: list = _load_json(_RULES_PATH, "visual_rules")
KNOWLEDGE_MODEL: dict = _load_json(_KNOWLEDGE_PATH, "knowledge_model")


def _rule_summary_from_python(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "display_name": rule.display_name,
        "description": rule.description,
        "trigger_summary": rule.trigger_summary,
        "trigger_criteria": rule.trigger_criteria,
        "reader_question": rule.reader_question,
        "visual_type": rule.visual_type,
        "source_label": "Python reasoning rule",
    }


def _rule_summary_from_json(rule: dict) -> dict:
    return {
        "id": rule.get("id", "json-rule"),
        "display_name": rule.get("display_name", rule.get("visual_type", "JSON keyword rule")),
        "description": rule.get("description", rule.get("reason", "Keyword rule.")),
        "trigger_summary": rule.get("trigger_summary", rule.get("description", rule.get("reason", "Keyword rule."))),
        "trigger_criteria": rule.get("trigger_criteria", []),
        "reader_question": "—",
        "visual_type": rule.get("visual_type", "Unknown"),
        "source_label": "JSON keyword rule",
    }


def get_rule_catalog() -> list[dict]:
    catalog = [_rule_summary_from_python(rule) for rule in PYTHON_RULES]
    catalog.extend(_rule_summary_from_json(rule) for rule in JSON_RULES)
    return sorted(catalog, key=lambda item: item["id"])

_ACTION_VERBS = {
    "click", "select", "open", "enter", "type", "choose", "navigate",
    "save", "apply", "check", "uncheck", "toggle", "expand", "collapse",
    "drag", "drop", "upload", "download", "import", "export", "verify",
    "confirm", "refresh", "review", "configure", "set", "enable", "disable",
    "generate", "create", "start", "stop", "retry", "continue", "proceed",
    "install", "deploy", "launch"
}

_UI_TERMS = {
    "button", "tab", "menu", "dialog", "window", "panel", "screen",
    "field", "input", "checkbox", "toggle", "switch", "dropdown",
    "list", "table", "grid", "row", "column", "toolbar", "sidebar",
    "banner", "page", "section", "form"
}

_CHECKPOINT_TERMS = {
    "verify", "confirm", "check", "validate", "review", "ensure",
    "status", "result", "expected", "successful", "visible", "enabled",
    "disabled", "running", "connected", "ready"
}

_DATA_FLOW_VERBS = {
    "send", "receive", "forward", "publish", "subscribe", "collect",
    "transfer", "sync", "synchronize", "export", "import", "push",
    "pull", "route", "transmit", "stream"
}

_NETWORK_NOUNS = {
    "plc", "hmi", "gateway", "connector", "server", "client", "cloud",
    "broker", "router", "switch", "network", "edge", "device", "controller",
    "runtime", "database", "bus", "mqtt", "opc ua"
}

_RELATION_PATTERNS = [
    r"(?P<src>[A-Za-z0-9_ /-]+?)\s+(?:connects to|is connected to|communicates with|sends to|publishes to|subscribes to|forwards to|routes to|transfers to)\s+(?P<dst>[A-Za-z0-9_ /-]+)",
    r"(?P<src>[A-Za-z0-9_ /-]+?)\s+(?:via|through)\s+(?P<dst>[A-Za-z0-9_ /-]+)",
]

# Signal extraction
# ─────────────────────────────────────────────

def _count(content: str, pattern: str) -> int:
    return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))


def _word_hits(content_lower: str, terms: set) -> int:
    total = 0
    for term in terms:
        if " " in term:
            total += content_lower.count(term)
        else:
            total += len(re.findall(r"\b" + re.escape(term) + r"\b", content_lower))
    return total


def _extract_steps(content: str) -> list[str]:
    numbered = re.findall(
        r"^\s*(?:\d+[\.)]|step\s+\d+)\s*(.+)$",
        content, re.MULTILINE | re.IGNORECASE
    )
    if numbered:
        return [s.strip() for s in numbered if s.strip()]

    inferred = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        first = re.sub(r"[^a-zA-Z]", "", line.split()[0]).lower() if line.split() else ""
        if first in _ACTION_VERBS:
            inferred.append(line)
    return inferred


def _count_relationships(content: str) -> int:
    seen = set()
    count = 0
    sentences = re.split(r"(?<=[.!?])\s+|\n", content)
    for sentence in sentences:
        s = sentence.strip().rstrip(".")
        for pattern in _RELATION_PATTERNS:
            m = re.match(pattern, s, re.IGNORECASE)
            if m:
                key = (m.group("src").strip().lower(), m.group("dst").strip().lower())
                if key not in seen:
                    seen.add(key)
                    count += 1
                break
    return count


def _count_conditional_branches(content: str) -> int:
    """Count distinct decision branches across sentence and numbered-step formats."""
    # Standard inline condition forms.
    inline_if = re.findall(r"\bif\b[^.]{5,120}(?:,|:|\bthen\b)", content, re.IGNORECASE)

    # Numbered decision steps common in manuals:
    # 2. If status is Connected, proceed.
    # 3. If status is Error, check cable.
    numbered_if = re.findall(r"^\s*\d+[\.)]\s*if\b.+$", content, re.IGNORECASE | re.MULTILINE)

    # Sentence-level if clauses with action verbs but no comma/colon delimiter.
    if_with_action = re.findall(
        r"\bif\b[^.]{5,120}\b(proceed|continue|check|retry|select|open|click|use|set|configure|return|stop)\b",
        content,
        re.IGNORECASE,
    )

    else_markers = re.findall(r"\b(otherwise|else|if not|alternatively)\b", content, re.IGNORECASE)

    if_count = max(len(inline_if), len(numbered_if), len(if_with_action))
    if if_count == 0:
        return 0

    return if_count + len(else_markers)


def _has_comparison(content: str) -> bool:
    """
    Detect side-by-side option comparison:
    'Use X for Y, use Z for W' or 'X vs Z' or
    two named protocols/options being contrasted.
    """
    vs_pattern = r"\b\w+\s+vs\.?\s+\w+\b"
    use_x_for = r"\buse\s+\w+\s+(?:for|when|if)\b.{10,80}\buse\s+\w+\s+(?:for|when|if)\b"
    return bool(
        re.search(vs_pattern, content, re.IGNORECASE) or
        re.search(use_x_for, content, re.IGNORECASE | re.DOTALL)
    )


def _has_network_nouns(content_lower: str) -> bool:
    return _word_hits(content_lower, _NETWORK_NOUNS) >= 1


def _has_code_block(content: str) -> bool:
    # Fenced code blocks: ``` ... ``` or ~~~ ... ~~~
    if re.search(r"```[\s\S]*?```|~~~[\s\S]*?~~~", content, re.MULTILINE):
        return True

    # Indented code-like blocks: at least 3 consecutive indented non-image lines.
    consecutive = 0
    for line in content.splitlines():
        if re.match(r"^(?: {4}|\t)\S", line):
            stripped = line.strip()
            if stripped.startswith("![") or stripped.startswith("!!!"):
                consecutive = 0
                continue
            consecutive += 1
            if consecutive >= 3:
                return True
        else:
            consecutive = 0

    return False


def _count_validation_gate_branches(content: str) -> int:
    """Detect procedural 'if successful, continue' validation gates (not real user choices)."""
    patterns = [
        r"\bif\b[^.]{0,80}\b(successful|succeeds|passed|valid|validated|active|ok)\b[^.]{0,120}\b(proceed|continue|click|save|export|validate|build|next)\b",
        r"\bif\b[^.]{0,120}\b(proceed|continue|click|save|export|validate|build|next)\b",
    ]
    matches = 0
    for pattern in patterns:
        matches = max(matches, len(re.findall(pattern, content, re.IGNORECASE)))
    return matches


def _count_choice_option_markers(content_lower: str) -> int:
    """Detect language that indicates user choice among alternatives."""
    markers = {
        "option", "options", "mode", "protocol", "connector type", "variant",
        "instead", "versus", "vs", "otherwise use", "alternatively", "either", "or"
    }
    return _word_hits(content_lower, markers)


def _count_ui_action_sentences(content: str) -> int:
    """Count sentences that start with a concrete UI action verb."""
    pattern = (
        r"(?:^|[.!?]\s+)"
        r"(?:please\s+)?"
        r"(click|select|open|enter|type|choose|navigate|save|apply|toggle|check|uncheck|expand|collapse|drag|drop|upload|download|import|export)\b"
    )
    return len(re.findall(pattern, content, re.IGNORECASE))


def compute_signals(content: str) -> dict:
    content_lower = content.lower()
    step_lines = _extract_steps(content)
    nested_steps = _count(content, r"^\s{2,}(?:[-*]|[a-z][\.)])")
    warnings = _count(content, r"\b(warning|caution|important|notice)\b")
    verifications = _count(content, r"\b(verify|validate|check status|confirm)\b")
    ui_interactions = _word_hits(content_lower, _UI_TERMS)
    action_verbs = _word_hits(content_lower, _ACTION_VERBS)
    data_flow_verbs = _word_hits(content_lower, _DATA_FLOW_VERBS)
    relationship_count = _count_relationships(content)
    conditional_branches = _count_conditional_branches(content)
    validation_gate_branches = _count_validation_gate_branches(content)
    choice_option_markers = _count_choice_option_markers(content_lower)
    ui_action_sentences = _count_ui_action_sentences(content)
    word_count = len(content.split())

    complexity_score = round(
        len(step_lines)
        + nested_steps * 1.5
        + warnings * 1.5
        + verifications * 1.2,
        1
    )

    # Density metrics: normalised per 100 words.
    # These replace brittle raw-count thresholds so that a section with
    # 3 UI terms in 20 words (dense) scores differently from one with
    # 3 UI terms in 200 words (sparse).
    word_count_safe = max(word_count, 1)
    ui_density           = round(ui_interactions        / word_count_safe * 100, 1)
    relationship_density = round(relationship_count     / word_count_safe * 100, 1)
    procedure_density    = round(len(step_lines)        / word_count_safe * 100, 1)
    decision_density     = round(conditional_branches   / word_count_safe * 100, 1)

    return {
        "step_lines": step_lines,
        "steps": len(step_lines),
        "nested_steps": nested_steps,
        "warnings": warnings,
        "verifications": verifications,
        "ui_interactions": ui_interactions,
        "action_verbs": action_verbs,
        "data_flow_verbs": data_flow_verbs,
        "relationship_count": relationship_count,
        "conditional_branches": conditional_branches,
        "validation_gate_branches": validation_gate_branches,
        "choice_option_markers": choice_option_markers,
        "ui_action_sentences": ui_action_sentences,
        "word_count": word_count,
        "complexity_score": complexity_score,
        # density metrics
        "ui_density": ui_density,
        "relationship_density": relationship_density,
        "procedure_density": procedure_density,
        "decision_density": decision_density,
        # boolean flags
        "has_network_nouns": _has_network_nouns(content_lower),
        "has_code_block": _has_code_block(content),
        "has_comparison": _has_comparison(content),
    }


# ─────────────────────────────────────────────
# Content classifier (lightweight — signals only)
# ─────────────────────────────────────────────

def classify_content(title: str, content: str, signals: dict) -> tuple[str, int]:
    """Two-pass classification: structural signals first, vocabulary as tie-breaker."""
    title_lower = title.lower()
    combined = (title + " " + content).lower()

    error_hits = len(re.findall(r"\b(troubleshoot|error|failure|issue|fault)\b", combined))

    structural_scores = {
        "Procedure": (
            signals["steps"] * 2
            + min(signals["action_verbs"], 8) // 2
            + min(signals["ui_interactions"], 8) // 3
            + min(signals["verifications"], 4)
        ),
        "Architecture": (
            signals["relationship_count"] * 3
            + (2 if signals.get("has_network_nouns") else 0)
            + min(signals["data_flow_verbs"], 4)
        ),
        "Troubleshooting": signals["conditional_branches"] * 2 + error_hits * 3,
        "Reference": (
            len(re.findall(r"\b(parameter|field|property|reference|api|table)\b", combined)) * 2
            + (1 if signals["steps"] == 0 else 0)
        ),
        "Concept": 1,
    }

    # Vocabulary/title tie-breaker adjusts close structural scores.
    tie_breakers = {
        "Procedure": len(re.findall(r"\b(procedure|steps|how to|configure|setup)\b", title_lower)),
        "Architecture": len(re.findall(r"\b(architecture|topology|system layout|integration|overview)\b", combined)),
        "Troubleshooting": error_hits,
        "Reference": len(re.findall(r"\b(reference|api|parameter|field)\b", title_lower)),
        "Concept": len(re.findall(r"\b(overview|introduction|behavior|concept)\b", title_lower)),
    }

    scored = {
        label: structural_scores[label] * 10 + min(tie_breakers[label], 3) * 3
        for label in structural_scores
    }
    best_label = max(scored, key=scored.get)
    best_score = scored[best_label]

    # Confidence scales with structural strength.
    if best_label == "Procedure":
        confidence = 95 if signals["steps"] >= 5 else (85 if signals["steps"] >= 3 else 70)
    elif best_label == "Architecture":
        confidence = min(92, 60 + signals["relationship_count"] * 10 + (8 if signals.get("has_network_nouns") else 0))
    elif best_label == "Troubleshooting":
        confidence = min(92, 60 + signals["conditional_branches"] * 10 + error_hits * 6)
    elif best_label == "Reference":
        confidence = 75
    else:
        confidence = 55

    # Guard weak structural outcomes from overconfident labels.
    if best_score < 20:
        return "Concept", 50

    return best_label, confidence


# ─────────────────────────────────────────────
# Visual worthiness gate
# Prevents recommending visuals for trivially
# simple content that doesn't need one.
# ─────────────────────────────────────────────

def _visual_worthiness_score(signals: dict, content_type: str, section_context: dict | None = None) -> tuple[int, str]:
    """Return graduated visual worthiness score (0-10) and rationale."""
    score = 5
    reasons = []

    if signals["word_count"] < 20:
        score -= 4
        reasons.append("Very short section")
    elif signals["word_count"] >= 80:
        score += 1

    if signals["steps"] >= 4:
        score += 2
        reasons.append("Multi-step procedure")
    elif signals["steps"] <= 1:
        score -= 1

    if signals["ui_interactions"] >= 4:
        score += 2
        reasons.append("Dense UI interactions")
    elif signals["ui_interactions"] == 0 and signals["steps"] <= 1:
        score -= 1

    if signals["relationship_count"] >= 2:
        score += 2
        reasons.append("Multiple explicit relationships")

    if signals["conditional_branches"] >= 2:
        score += 2
        reasons.append("Decision branches present")

    if signals["warnings"] >= 1 or signals["verifications"] >= 2:
        score += 1

    if (
        signals["steps"] <= 1
        and signals["ui_interactions"] <= 2
        and signals["word_count"] < 25
        and signals["warnings"] == 0
        and signals["relationship_count"] == 0
        and signals["conditional_branches"] == 0
    ):
        score -= 3
        reasons.append("Single-parameter/simple instruction")

    if (
        content_type == "Reference"
        and signals["steps"] == 0
        and signals["ui_interactions"] == 0
        and signals["word_count"] < 60
    ):
        score -= 2
        reasons.append("Short reference entry")

    if section_context:
        # Lightweight adjacent-section context boost for prerequisites before long procedures.
        if section_context.get("next_steps", 0) >= 6 and signals["word_count"] >= 20:
            score += 1
            reasons.append("Adjacent long procedure context")

    score = max(0, min(10, score))
    reason = ", ".join(reasons[:3]) if reasons else "Balanced content"
    return score, reason


# ─────────────────────────────────────────────
# Placement suggestion
# ─────────────────────────────────────────────

def _suggest_placement(visual_type: str, content_type: str, signals: dict) -> dict | None:
    diagram_types = {
        "Architecture Diagram", "Topology Diagram", "Data Flow Diagram",
        "Workflow Diagram", "Decision Tree", "Comparison Table", "Sequence Diagram",
    }
    screenshot_types = {"Screenshot", "Configuration Screenshot", "Annotated Screenshot", "GIF / Video Tutorial"}

    if visual_type in diagram_types:
        return {
            "placement": "before_section",
            "display_text": "Before the procedure steps — context first",
            "reason": "Diagram builds mental model before users start following steps",
        }

    if visual_type in screenshot_types:
        steps = signals["step_lines"]
        for i, step in enumerate(steps):
            if any(t in step.lower() for t in _UI_TERMS):
                return {
                    "placement": "after_step",
                    "step_number": i + 1,
                    "step_text": step[:60],
                    "display_text": f"After step {i + 1}: {step[:60]}",
                    "reason": "UI interaction step — screenshot confirms correct state",
                }
        for i, step in enumerate(steps):
            if any(t in step.lower() for t in _CHECKPOINT_TERMS):
                return {
                    "placement": "after_step",
                    "step_number": i + 1,
                    "step_text": step[:60],
                    "display_text": f"After step {i + 1}: {step[:60]}",
                    "reason": "Checkpoint step — screenshot confirms success state",
                }

    return None


# ─────────────────────────────────────────────
# Artifact generation (unchanged from v1 — 
# still generates Mermaid/PlantUML where possible)
# ─────────────────────────────────────────────

def _sanitize(label: str) -> str:
    label = re.sub(r"\s+", " ", label.strip()).strip(" -:;,.()[]{}")
    return label.replace('"', "'")


def _shorten_step(step: str) -> str:
    # Remove leading numbering
    s = re.sub(r"^\s*(?:\d+[\.)]|step\s+\d+:?)\s*", "", step, flags=re.IGNORECASE)
    # Truncate at punctuation only, keeping the phrase intact
    parts = re.split(r"\.|,|;|\(", s)
    short = parts[0].strip()
    words = short.split()
    if len(words) > 8:
        short = " ".join(words[:8]) + "..."
    return short.strip()


def _generation_confidence(
    visual_type: str,
    signals: dict,
    generated_artifact: dict | None,
) -> tuple[int, str]:
    """Score confidence for auto-generated visual content quality (0-100)."""
    if visual_type == "Decision Tree":
        # Disabled intentionally until decision extraction is robust.
        return 0, "Auto-generation is disabled for decision trees (conditional extraction is unreliable). Use placement hint to author manually."

    if not generated_artifact:
        return 25, "No generated artifact; rely on placement hint and draft manually."

    if visual_type in {"Workflow Diagram", "Flowchart", "Sequence Diagram"}:
        steps = signals.get("steps", 0)
        warnings = signals.get("warnings", 0)
        verifications = signals.get("verifications", 0)
        if steps >= 6:
            reason = f"{steps} procedural steps detected — sufficient structure for reliable generation."
            if warnings:
                reason += f" {warnings} warning(s) add ordering constraints."
            return 85, reason
        if steps >= 3:
            reason = f"{steps} procedural steps detected; generation is a reasonable draft."
            if verifications:
                reason += f" {verifications} verification step(s) reduce ambiguity."
            return 70, reason
        return 55, f"{steps} step(s) detected — too few for confident generation; verify output carefully."

    if visual_type in {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram"}:
        rel = signals.get("relationship_count", 0)
        data_flow = signals.get("data_flow_verbs", 0)
        if rel >= 3:
            return 88, f"{rel} explicit component relationships detected — diagram should be accurate."
        if rel >= 1:
            reason = f"{rel} explicit relationship(s) detected."
            if data_flow:
                reason += f" {data_flow} data-flow verb(s) add directional specificity."
            return 72, reason
        return 50, "No explicit A→B relationships found; generated diagram is inferred from vocabulary only."

    if visual_type in {"Screenshot", "Configuration Screenshot", "Annotated Screenshot"}:
        ui = signals.get("ui_interactions", 0)
        return 80, f"Capture specification generated from {ui} detected UI interaction(s); validate against live interface."

    return 65, "Generation available; validate output against source text before publishing."


def _placement_confidence(
    recommendation_confidence: int,
    placement_hint: dict | None,
) -> tuple[int, str]:
    """Score confidence for placement recommendation separately from content generation."""
    if not placement_hint:
        return max(35, recommendation_confidence - 30), "No explicit placement hint for this visual type."

    placement = placement_hint.get("placement")
    if placement == "after_step":
        return min(98, recommendation_confidence + 5), "Anchored to an explicit procedural step."
    if placement == "before_section":
        return min(95, recommendation_confidence + 3), "Anchored to section context before task execution."
    return max(45, recommendation_confidence - 10), "Placement hint is generic; verify location manually."

def _build_workflow_artifact(title: str, signals: dict) -> dict | None:
    steps = signals.get("step_lines", [])
    if len(steps) < 2:
        return None
    svg = generate_simple_flow_svg(title, steps, signals)
    if not svg:
        return None

    return {
        "artifact_type": "workflow_svg",
        "format": "svg",
        "title": title,
        "svg": svg,
        "summary": f"Generated from {len(steps)} steps.",
    }


def _build_sequence_artifact(title: str, signals: dict) -> dict | None:
    steps = signals.get("step_lines", [])
    if len(steps) < 2:
        return None

    mermaid = ["sequenceDiagram"]
    mermaid.append("    participant System")
    mermaid.append("    participant Component")
    for i, step in enumerate(steps):
        clean_step = _sanitize(step[:40])
        mermaid.append(f"    System->>Component: {i+1}. {clean_step}")

    return {
        "artifact_type": "sequence",
        "title": title,
        "mermaid": "\n".join(mermaid),
        "summary": f"Generated from {len(steps)} steps.",
    }


def _build_decision_artifact(title: str, content: str) -> dict | None:
    # Decision-tree extraction remains heuristic and can degrade trust when
    # text contains validation gates rather than true reader choices.
    # Keep recommendation, but avoid auto-generating weak diagrams.
    return None


def _build_generated_artifact(
    visual_type: str,
    title: str,
    content: str,
    signals: dict,
    content_type: str,
    placement_hint: dict | None = None,
) -> dict | None:
    if visual_type in {"Workflow Diagram", "Flowchart"}:
        return _build_workflow_artifact(title, signals)
    if visual_type == "Sequence Diagram":
        return _build_sequence_artifact(title, signals)
    if visual_type == "Decision Tree":
        return _build_decision_artifact(title, content)
    if visual_type in {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram"}:
        svg = generate_architecture_diagram(title, content)
        if not svg:
            return None
        return {
            "artifact_type": "architecture_svg",
            "format": "svg",
            "title": title,
            "svg": svg,
            "summary": "Generated by deterministic component and relationship extraction.",
        }
    if visual_type in {"Screenshot", "Configuration Screenshot", "Annotated Screenshot"}:
        # Build screenshot specs from the most relevant interaction step when available.
        step_context = content
        placement = "Before"
        step_number = 1
        if placement_hint and placement_hint.get("placement") == "after_step":
            step_context = placement_hint.get("step_text", content)
            placement = "After"
            step_number = int(placement_hint.get("step_number", 1))

        spec = generate_screenshot_specification(
            step_context=step_context,
            placement=placement,
            step_number=step_number,
            section_title=title,
            placement_text=placement_hint.get("display_text", "") if placement_hint else "",
        )
        if not spec and step_context != content:
            # Retry with full section context when the chosen step is too terse.
            spec = generate_screenshot_specification(
                step_context=content,
                placement=placement,
                step_number=step_number,
                section_title=title,
                placement_text=placement_hint.get("display_text", "") if placement_hint else "",
            )
        if not spec:
            return None
        return {
            "artifact_type": "screenshot_specification",
            "format": "json",
            "title": title,
            "specification": spec.to_dict(),
            "summary": "Generated screenshot specification with capture guidelines and verification checklist.",
        }
    return None


def _extract_orphan_components(visual_type: str, content: str, generated_artifact: dict | None) -> list[str]:
    if visual_type in {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram"} and not generated_artifact:
        from generators.architecture_parser import _extract_component_mentions, _load_knowledge_model
        knowledge = _load_knowledge_model()
        orphans = _extract_component_mentions(content, knowledge)
        return sorted(list({o['name'] for o in orphans}))
    return []


def _generate_alt_text(spec: dict | None, placement_hint: dict | None) -> str:
    """Draft descriptive alt text from the screenshot specification."""
    if spec:
        purpose = spec.get("purpose", "").strip().rstrip(".")
        focus = spec.get("focus_area", "").strip()
        if purpose and focus:
            return f"{purpose} - {focus} highlighted"
        if purpose:
            return purpose
    if placement_hint and placement_hint.get("placement") == "after_step":
        step_text = placement_hint.get("step_text", "").strip().rstrip(".")
        if step_text:
            return f"UI state after: {step_text}"
    return "Screenshot of the required UI state"


def _generate_screenshot_filename(spec: dict | None, placement_hint: dict | None) -> str:
    """Generate a slug-based filename from spec context and step."""
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-{2,}", "-", text)
        return text.strip("-")[:50]

    parts: list[str] = []

    if spec:
        page = spec.get("context", {}).get("page", "")
        if page and page.lower() not in ("current page", ""):
            parts.append(slugify(page))

    if placement_hint and placement_hint.get("placement") == "after_step":
        step_text = placement_hint.get("step_text", "").strip()
        if step_text:
            stop_words = {"you", "have", "the", "a", "an", "your", "from", "to", "in", "on", "of", "is", "are", "and"}
            words = re.sub(r"[^\w\s]", "", step_text).split()
            keywords = [w.lower() for w in words if w.lower() not in stop_words][:5]
            if keywords:
                parts.append("-".join(keywords))

    if parts:
        return "-".join(parts) + ".png"
    return "screenshot.png"


def _build_insertion_snippet(visual_type: str, generated_artifact: dict | None, placement_hint: dict | None) -> str | None:
    placement = placement_hint.get("display_text") if placement_hint else "At the recommended location in this section"

    if generated_artifact and generated_artifact.get("mermaid"):
        mermaid = generated_artifact["mermaid"].strip()
        return (
            f"<!-- Insert {visual_type}: {placement} -->\n"
            f"```mermaid\n{mermaid}\n```"
        )

    if generated_artifact and generated_artifact.get("svg"):
        filename = "flow.svg"
        if generated_artifact.get("artifact_type") == "architecture_svg":
            filename = "architecture.svg"
        return (
            f"<!-- Insert {visual_type}: {placement} -->\n"
            f"<!-- Save as docs/assets/{filename} and embed: -->\n"
            f"![{visual_type}](../assets/{filename})"
        )

    if visual_type == "GIF / Video Tutorial":
        return (
            f"<!-- Insert {visual_type}: {placement} -->\n"
            "![describe-animation](../media/your-animation.gif)"
        )

    if visual_type in {"Screenshot", "Configuration Screenshot", "Annotated Screenshot"}:
        spec = generated_artifact.get("specification") if generated_artifact else None
        alt_text = _generate_alt_text(spec, placement_hint)
        filename = _generate_screenshot_filename(spec, placement_hint)
        return (
            f"<!-- Insert {visual_type}: {placement} -->\n"
            f"![{alt_text}](../media/{filename})"
        )

    if visual_type == "Decision Tree":
        return (
            f"<!-- Insert Decision Tree: {placement} -->\n"
            "```mermaid\n"
            "flowchart TD\n"
            "A{Condition?}\n"
            "A -->|Yes| B[Proceed]\n"
            "A -->|No| C[Alternative action]\n"
            "```"
        )

    return None


# ─────────────────────────────────────────────
# Existing-visual detection
# ─────────────────────────────────────────────

def _detect_existing_assets(content: str) -> dict:
    md_images = _count(content, r"!\[[^\]]*\]\([^\)]+\)")
    html_images = _count(content, r"<img\b")
    
    # We no longer count text words like "diagram" or "screenshot" 
    # as existing assets to prevent false positives and double-counting.
    total = md_images + html_images
    
    return {
        "screenshot": total, # Generic bucket for existing visuals
        "diagram": total,
        "gif": total,
        "total": total,
    }


def _detect_accessibility_issues(content: str) -> list[str]:
    issues = []
    
    # 1. Markdown empty alt text: ![]() or ![ ]()
    md_missing_alt = re.findall(r"!\[\s*\]\(([^\)]+)\)", content)
    for src in md_missing_alt:
        issues.append(f"Markdown image '{src}' is missing Alt-Text.")
        
    # 2. HTML empty or missing alt text
    html_images = re.findall(r"<img[^>]+>", content, re.IGNORECASE)
    for img_tag in html_images:
        alt_match = re.search(r'alt=["\'](.*?)["\']', img_tag, re.IGNORECASE)
        if not alt_match or alt_match.group(1).strip() == "":
            src_match = re.search(r'src=["\'](.*?)["\']', img_tag, re.IGNORECASE)
            src = src_match.group(1) if src_match else "unknown"
            issues.append(f"HTML image '{src}' is missing an alt attribute.")
            
    return issues


def _gap_analysis(visual_type: str, existing: dict) -> dict:
    family_map = {
        "Screenshot": "screenshot", "Configuration Screenshot": "screenshot",
        "Annotated Screenshot": "screenshot", "GIF / Video Tutorial": "gif", "GIF Tutorial": "gif",
        "Architecture Diagram": "diagram", "Topology Diagram": "diagram",
        "Data Flow Diagram": "diagram", "Workflow Diagram": "diagram",
        "Decision Tree": "diagram", "Flowchart": "diagram",
        "Comparison Table": "diagram", "Mapping Table": "diagram", "Sequence Diagram": "diagram",
    }
    family = family_map.get(visual_type, "other")
    existing_count = existing.get(family, 0)
    gap_message = "No additional visuals needed" if existing_count >= 1 else "Visual recommended"
    coverage = int(existing_count / 1 * 100)
    return {
        "family": family,
        "existing_count": existing_count,
        "gap_message": gap_message,
        "coverage_display": f"Coverage: {existing_count}/1 ({coverage}%)",
    }



# ─────────────────────────────────────────────
# Priority and confidence helpers
# ─────────────────────────────────────────────

def _priority(confidence: int) -> str:
    if confidence >= 80:
        return "High"
    if confidence >= 55:
        return "Medium"
    return "Low"


def _confidence_category(confidence: int) -> str:
    if confidence >= 80:
        return "High"
    if confidence >= 50:
        return "Medium"
    return "Low"


# ─────────────────────────────────────────────
# JSON rule runner
# ─────────────────────────────────────────────

def _run_json_rules(
    content: str, signals: dict, content_type: str
) -> list[dict]:
    content_lower = content.lower()
    results = []

    for rule in JSON_RULES:
        # VR007 (Code Example) requires structural code context.
        if rule.get("id") == "VR007" and not signals.get("has_code_block", False):
            continue

        # Keyword matching with proper word boundaries
        matched = []
        for kw in rule.get("keywords", []):
            kw_lower = kw.lower()
            if " " in kw_lower:
                pattern = r"\b" + r"\s+".join(re.escape(w) for w in kw_lower.split()) + r"\b"
                if re.search(pattern, content_lower):
                    matched.append(kw)
            else:
                if re.search(r"\b" + re.escape(kw_lower) + r"\b", content_lower):
                    matched.append(kw)

        min_hits = rule.get("min_keyword_hits", 1)
        if len(matched) < min_hits:
            continue

        min_words = rule.get("min_words")
        if min_words and signals["word_count"] < min_words:
            continue

        allowed_types = rule.get("content_types", [])
        type_match = not allowed_types or content_type in allowed_types

        base = rule.get("confidence_base", 65)
        confidence = base if type_match else max(base - 20, 30)

        results.append({
            "visual_type": rule["visual_type"],
            "reader_question": "—",
            "reason": rule["reason"],
            "confidence": confidence,
            "confidence_category": _confidence_category(confidence),
            "priority": _priority(confidence),
            "evidence": [f"Keywords matched: {', '.join(matched[:4])}"],
            "rationale": rule["reason"],
            "source": f"json:{rule['id']}",
            "rule_summary": _rule_summary_from_json(rule),
        })

    return results


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def detect_visuals(title: str, content: str, section_context: dict | None = None) -> list[dict]:
    signals = compute_signals(content)
    content_type, content_type_confidence = classify_content(title, content, signals)
    existing_assets = _detect_existing_assets(content)
    worthiness_score, worthiness_reason = _visual_worthiness_score(signals, content_type, section_context)

    # Hard skip for very low worthiness (0-2) to keep simple content text-only.
    if worthiness_score < 3:
        return [{
            "visual_type": "No recommendation",
            "reader_question": "—",
            "reason": "No strong visual value for this section",
            "confidence": 0,
            "confidence_category": "Low",
            "priority": "Low",
            "generator": "none",
            "plantuml_code": None,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "worthiness_score": worthiness_score,
            "evidence": [worthiness_reason],
            "rationale": worthiness_reason,
            "source": "worthiness_gate",
            "existing_visuals": existing_assets,
            "gap_message": "No visual needed",
            "gap_coverage": "Coverage: n/a",
            "existing_count": existing_assets["total"],
            "required_count": 0,
            "placement_hint": None,
            "generated_artifact": None,
            "suggested_content": "Keep text-only.",
        }]

    # ── Python rules ───────────────────────────
    python_hits: list[dict] = []
    for rule in PYTHON_RULES:
        result: RuleResult | None = rule.match(signals)
        if result is None:
            continue

        gap = _gap_analysis(result.visual_type, existing_assets)
        # Reduce confidence if visual type already covered
        confidence = result.confidence
        if gap["existing_count"] >= 1:
            confidence = max(0, confidence - 20)
        confidence = max(0, min(100, confidence + (worthiness_score - 5) * 3))
        placement_hint = _suggest_placement(result.visual_type, content_type, signals)
        placement_confidence, placement_confidence_reason = _placement_confidence(confidence, placement_hint)
        generated_artifact = _build_generated_artifact(
            result.visual_type, title, content, signals, content_type, placement_hint
        )
        generation_confidence, generation_confidence_reason = _generation_confidence(
            result.visual_type, signals, generated_artifact
        )
        insertion_snippet = _build_insertion_snippet(result.visual_type, generated_artifact, placement_hint)
        generator = _assign_generator(result.visual_type)
        plantuml_code = (
            generate_plantuml(result.visual_type, title, signals, content)
            if generator == "plantuml" else None
        )

        rule_summary = _rule_summary_from_python(rule)
        why_trace = [
            f"Placement confidence: {placement_confidence}% ({placement_confidence_reason})",
            f"Generation confidence: {generation_confidence}% ({generation_confidence_reason})",
            f"Worthiness score: {worthiness_score}/10 ({worthiness_reason})",
        ]
        if result.evidence:
            why_trace.append(f"Signals: {result.evidence[0]}")

        python_hits.append({
            "visual_type": result.visual_type,
            "reader_question": result.reader_question,
            "reason": result.rationale,
            "confidence": confidence,
            "confidence_category": _confidence_category(confidence),
            # priority is set by the rule directly (independent of confidence)
            "priority": result.priority,
            "reader_value": result.reader_value,
            "generator": generator,
            "plantuml_code": plantuml_code,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "worthiness_score": worthiness_score,
            "evidence": result.evidence,
            "rationale": result.rationale,
            "source": f"python:{rule.id}",
            "rule_summary": rule_summary,
            "existing_visuals": existing_assets,
            "gap_message": gap["gap_message"],
            "gap_coverage": gap["coverage_display"],
            "existing_count": gap["existing_count"],
            "required_count": 1,
            "placement_hint": placement_hint,
            "placement_confidence": placement_confidence,
            "placement_confidence_reason": placement_confidence_reason,
            "generation_confidence": generation_confidence,
            "generation_confidence_reason": generation_confidence_reason,
            "generated_artifact": generated_artifact,
            "orphan_components": _extract_orphan_components(result.visual_type, content, generated_artifact),
            "insertion_snippet": insertion_snippet,
            "suggested_content": _suggest_content(result.visual_type, title, signals, placement_hint),
            "why_trace": why_trace,
        })

    # ── JSON rules ─────────────────────────────
    json_hits = _run_json_rules(content, signals, content_type)
    for hit in json_hits:
        gap = _gap_analysis(hit["visual_type"], existing_assets)
        if gap["existing_count"] >= 1:
            hit["confidence"] = max(0, hit["confidence"] - 20)
        hit["confidence"] = max(0, min(100, hit["confidence"] + (worthiness_score - 5) * 3))
        placement_hint = _suggest_placement(hit["visual_type"], content_type, signals)
        placement_confidence, placement_confidence_reason = _placement_confidence(hit["confidence"], placement_hint)
        generated_artifact = _build_generated_artifact(
            hit["visual_type"], title, content, signals, content_type, placement_hint
        )
        generation_confidence, generation_confidence_reason = _generation_confidence(
            hit["visual_type"], signals, generated_artifact
        )
        insertion_snippet = _build_insertion_snippet(hit["visual_type"], generated_artifact, placement_hint)
        generator = _assign_generator(hit["visual_type"])
        plantuml_code = (
            generate_plantuml(hit["visual_type"], title, signals, content)
            if generator == "plantuml" else None
        )
        why_trace = [
            f"Placement confidence: {placement_confidence}% ({placement_confidence_reason})",
            f"Generation confidence: {generation_confidence}% ({generation_confidence_reason})",
            f"Worthiness score: {worthiness_score}/10 ({worthiness_reason})",
        ]
        if hit.get("evidence"):
            why_trace.append(f"Signals: {hit['evidence'][0]}")
        hit.update({
            "generator": generator,
            "plantuml_code": plantuml_code,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "worthiness_score": worthiness_score,
            # JSON rules don't compute reader_value; default to 3 (moderate benefit)
            "reader_value": hit.get("reader_value", 3),
            "existing_visuals": existing_assets,
            "gap_message": gap["gap_message"],
            "gap_coverage": gap["coverage_display"],
            "existing_count": gap["existing_count"],
            "required_count": 1,
            "placement_hint": placement_hint,
            "placement_confidence": placement_confidence,
            "placement_confidence_reason": placement_confidence_reason,
            "generation_confidence": generation_confidence,
            "generation_confidence_reason": generation_confidence_reason,
            "generated_artifact": generated_artifact,
            "orphan_components": _extract_orphan_components(hit["visual_type"], content, generated_artifact),
            "insertion_snippet": insertion_snippet,
            "suggested_content": _suggest_content(hit["visual_type"], title, signals, placement_hint),
            "why_trace": why_trace,
        })

    # ── Merge and deduplicate ──────────────────
    # Python rules win on type conflicts
    all_hits = python_hits + json_hits
    seen_types: set[str] = set()
    deduped: list[dict] = []
    for hit in sorted(all_hits, key=lambda h: h["confidence"], reverse=True):
        if hit["visual_type"] in seen_types:
            continue
        seen_types.add(hit["visual_type"])
        # If this visual family is already covered (for example existing screenshots),
        # do not recommend another visual of the same family.
        if hit["gap_message"] == "No additional visuals needed" and hit.get("existing_count", 0) >= 1:
            continue
        deduped.append(hit)

    # ── Accessibility Auditing ─────────────────
    a11y_issues = _detect_accessibility_issues(content)
    if a11y_issues:
        a11y_card = {
            "visual_type": "Accessibility Warning",
            "reader_question": "Can screen readers describe this image?",
            "reason": "Missing Alt-Text violates accessibility compliance.",
            "confidence": 100,
            "confidence_category": "High",
            "priority": "High",
            "reader_value": 5,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "worthiness_score": 10,
            "evidence": a11y_issues,
            "rationale": "Missing Alt-Text violates accessibility compliance and hurts SEO.",
            "source": "a11y_auditor",
            "existing_visuals": existing_assets,
            "gap_message": f"{len(a11y_issues)} compliance issue(s)",
            "gap_coverage": "Action Required",
            "existing_count": 0,
            "required_count": len(a11y_issues),
            "placement_hint": None,
            "placement_confidence": 100,
            "placement_confidence_reason": "Accessibility diagnostics are direct checks.",
            "generation_confidence": 0,
            "generation_confidence_reason": "No generated visual for accessibility warnings.",
            "generated_artifact": None,
            "orphan_components": [],
            "insertion_snippet": "<!-- Correct format: ![Descriptive Text](url) -->",
            "suggested_content": "Add descriptive Alt-Text to the identified images so screen readers can interpret them.",
            "why_trace": [
                "Rule fired: a11y_auditor",
                "Placement confidence: 100% (direct static validation)",
                "Generation confidence: 0% (no generated artifact)",
            ],
        }
        deduped.insert(0, a11y_card)

    # ── No results fallback ────────────────────
    if not deduped:
        return [{
            "visual_type": "No recommendation",
            "reader_question": "—",
            "reason": "No strong visual signal detected in this section",
            "confidence": 0,
            "confidence_category": "Low",
            "priority": "Low",
            "generator": "none",
            "plantuml_code": None,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "worthiness_score": worthiness_score,
            "evidence": ["No pattern thresholds met"],
            "rationale": f"Section may be self-explanatory as text ({worthiness_reason}).",
            "source": "fallback",
            "existing_visuals": existing_assets,
            "gap_message": "No visual needed",
            "gap_coverage": "Coverage: n/a",
            "existing_count": existing_assets["total"],
            "required_count": 0,
            "placement_hint": None,
            "generated_artifact": None,
            "orphan_components": [],
            "insertion_snippet": None,
            "suggested_content": "Keep text-only unless complexity increases.",
        }]

    return deduped[:3]


# ─────────────────────────────────────────────
# Suggested content generator
# ─────────────────────────────────────────────

def _suggest_content(visual_type: str, title: str, signals: dict, placement_hint: dict | None = None) -> str:
    steps = signals["step_lines"][:8]

    if visual_type in {"Workflow Diagram", "Sequence Diagram"}:
        if steps:
            return f"Workflow for '{title}': " + " → ".join(steps[:6])
        return "Show start → action sequence → verification → end states."

    if visual_type in {"Screenshot", "Configuration Screenshot", "Annotated Screenshot"}:
        if placement_hint and placement_hint.get("placement") == "after_step":
            step_text = placement_hint.get("step_text", "").strip()
            if step_text:
                return (
                    f"Capture immediately after this action: {step_text}. Show the clicked control and resulting active state. "
                    "Keep the page context (header/tab) visible and annotate the selected row, field, or button."
                )
        return (
            "Capture the UI immediately after the key click or selection. "
            "Show both the control used and the resulting state, then annotate the active element."
        )

    if visual_type in {"Architecture Diagram", "Topology Diagram"}:
        return "Show all named components and their connections. Label each channel or protocol."

    if visual_type == "Data Flow Diagram":
        return "Show source component → transformation → destination. Mark publish/subscribe paths."

    if visual_type == "Decision Tree":
        return "Root node: the decision condition. Branch Yes/No to outcomes. Keep to 2–3 levels."

    if visual_type == "Comparison Table":
        return "Columns: Option, Use when, Advantage, Limitation. One row per option."

    if visual_type == "Mapping Table":
        return "Columns: Source field, Target field, Data type, Constraint, Notes."

    if visual_type == "Illustration":
        return "Show the physical assembly with callouts for each component and connection point."

    if visual_type == "Code Example":
        return "Provide a minimal working example with inline comments on each key field."

    return "Provide a concise visual that reduces cognitive load for the core concept in this section."


# ─────────────────────────────────────────────
# Generator assignment
# Maps each visual type to the tool that should
# produce it.  The orchestrator reads this field
# to dispatch to the correct MCP server.
# ─────────────────────────────────────────────

_GENERATOR_MAP: dict[str, str] = {
    # Linear workflows render better as native SVG
    "Workflow Diagram":       "svg_flow",
    "Sequence Diagram":       "plantuml",
    "Decision Tree":          "manual",
    "Architecture Diagram":   "svg_architecture",
    "Topology Diagram":       "svg_architecture",
    "Data Flow Diagram":      "svg_architecture",
    "Flowchart":              "svg_flow",
    # Table types — Mermaid renders inline Markdown tables cleanly
    "Comparison Table":       "mermaid",
    "Mapping Table":          "mermaid",
    # Physical/UI capture — requires a browser session
    "Screenshot":             "browser",
    "Configuration Screenshot": "browser",
    "Annotated Screenshot":   "browser",
    "GIF / Video Tutorial":   "browser",
    # Lookup in the documentation asset repository
    "Illustration":           "filesystem",
    "Code Example":           "filesystem",
}


def _assign_generator(visual_type: str) -> str:
    """Return the generator key for a given visual type.  Falls back to 'none'."""
    return _GENERATOR_MAP.get(visual_type, "none")
