"""
Reader-task-driven visual recommendation rules.

Each rule answers one question the reader is trying to answer.
Rules are Python objects with a match() function that receives
pre-computed signals and returns a RuleResult or None.

Signal contract (all fields guaranteed by compute_signals()):
    steps              int   — numbered/inferred procedural steps
    ui_interactions    int   — click/select/navigate/open/etc. hits
    relationship_count int   — explicit A→B relationship sentences
    conditional_branches int — distinct if/else/otherwise branches
    word_count         int   — total words in section
    complexity_score   float — weighted step complexity
    step_lines         list  — extracted step text strings
    has_network_nouns  bool  — PLC/gateway/connector/hub/cloud present
    has_comparison     bool  — two named options being contrasted
    action_verbs       int   — action-verb count
    verifications      int   — verify/validate/confirm hits
    warnings           int   — warning/caution/important hits
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class RuleResult:
    visual_type: str
    reader_question: str       # The user question this answers
    confidence: int            # 0–100
    priority: str              # High / Medium / Low
    evidence: list             # Human-readable signal explanations
    rationale: str             # One sentence why this visual helps
    source: str = "python"


@dataclass
class Rule:
    id: str
    reader_question: str
    visual_type: str
    description: str
    match: Callable            # (signals: dict) -> Optional[RuleResult]


# ─────────────────────────────────────────────
# Helper: confidence from evidence strength
# ─────────────────────────────────────────────

def _confidence(base: int, boosts: list[int]) -> int:
    return min(100, base + sum(boosts))


# ─────────────────────────────────────────────
# PR001 — "What is this?"
# Concept/overview sections that describe a
# system or component without procedural steps.
# Visual: Architecture Diagram or Concept Diagram
# ─────────────────────────────────────────────

def _match_pr001(signals: dict) -> Optional[RuleResult]:
    # Must have at least one relationship, not be a procedure
    rel = signals["relationship_count"]
    steps = signals["steps"]
    words = signals["word_count"]
    data_flow_score = signals.get("data_flow_verbs", 0)
    has_network = signals.get("has_network_nouns", False)

    if rel < 1:
        return None

    # Leave strongly connected/networked sections to PR005.
    if rel >= 2 and (has_network or data_flow_score >= 1):
        return None

    # Procedures explain steps, not systems — skip
    if steps >= 4:
        return None

    # Too short to warrant a diagram (single sentence mention)
    if words < 30:
        return None

    evidence = [f"{rel} system relationship(s) described"]
    boosts = []

    if rel >= 2:
        boosts.append(15)
        evidence.append("Multiple components described together")

    if signals.get("has_network_nouns"):
        boosts.append(10)
        evidence.append("Network/edge component vocabulary detected")

    if words >= 80:
        boosts.append(5)
        evidence.append(f"Section is {words} words — concept needs visual anchor")

    confidence = _confidence(55, boosts)
    priority = "High" if confidence >= 75 else "Medium"

    return RuleResult(
        visual_type="Architecture Diagram",
        reader_question="What is this?",
        confidence=confidence,
        priority=priority,
        evidence=evidence,
        rationale="Reader needs a mental model of the system before reading further.",
    )


PR001 = Rule(
    id="PR001",
    reader_question="What is this?",
    visual_type="Architecture Diagram",
    description="Overview sections describing a system or component relationship.",
    match=_match_pr001,
)


# ─────────────────────────────────────────────
# PR002 — "Where do I click?"
# Sections with dense UI interaction sequences.
# Visual: Screenshot (or Annotated Screenshot)
# ─────────────────────────────────────────────

def _match_pr002(signals: dict) -> Optional[RuleResult]:
    ui = signals["ui_interactions"]
    steps = signals["steps"]

    # Need meaningful UI interaction density
    if ui < 3:
        return None

    evidence = [f"{ui} UI interaction terms detected"]
    boosts = []

    if steps >= 3:
        boosts.append(10)
        evidence.append(f"{steps} steps guide user through the UI")

    if ui >= 6:
        boosts.append(15)
        evidence.append("High UI density — reader needs visual confirmation")

    if signals.get("verifications", 0) >= 1:
        boosts.append(5)
        evidence.append("Verification step present — screenshot confirms success state")

    # Single-parameter configs don't need a screenshot
    if steps <= 1 and ui <= 3 and signals["word_count"] < 25:
        return None

    confidence = _confidence(60, boosts)
    priority = "High" if ui >= 5 else "Medium"

    return RuleResult(
        visual_type="Screenshot",
        reader_question="Where do I click?",
        confidence=confidence,
        priority=priority,
        evidence=evidence,
        rationale="Reader needs to see the exact UI state to navigate confidently.",
    )


PR002 = Rule(
    id="PR002",
    reader_question="Where do I click?",
    visual_type="Screenshot",
    description="UI navigation sequences where readers need to see the interface.",
    match=_match_pr002,
)


# ─────────────────────────────────────────────
# PR003 — "What happens next?"
# Multi-step procedures with clear sequence.
# Visual: Workflow Diagram
# ─────────────────────────────────────────────

def _match_pr003(signals: dict) -> Optional[RuleResult]:
    steps = signals["steps"]
    complexity = signals["complexity_score"]

    # Needs a meaningful sequence
    if steps < 4:
        return None

    evidence = [f"{steps} procedural steps detected"]
    boosts = []

    if steps >= 7:
        boosts.append(20)
        evidence.append("Long procedure — workflow diagram reduces cognitive load")
    elif steps >= 5:
        boosts.append(10)
        evidence.append("Medium-length procedure benefits from visual sequence")

    if complexity >= 8:
        boosts.append(10)
        evidence.append(f"Complexity score {complexity} — nested or branching steps present")

    if signals.get("verifications", 0) >= 2:
        boosts.append(5)
        evidence.append("Multiple verification checkpoints — sequence needs to be visible")

    if signals.get("warnings", 0) >= 1:
        boosts.append(5)
        evidence.append("Warning present — reader needs orientation to not skip critical steps")

    confidence = _confidence(55, boosts)
    priority = "High" if steps >= 7 else "Medium"

    return RuleResult(
        visual_type="Workflow Diagram",
        reader_question="What happens next?",
        confidence=confidence,
        priority=priority,
        evidence=evidence,
        rationale="Reader needs to see the full sequence to understand where they are in the process.",
    )


PR003 = Rule(
    id="PR003",
    reader_question="What happens next?",
    visual_type="Workflow Diagram",
    description="Multi-step procedures where sequence and completeness matter.",
    match=_match_pr003,
)


# ─────────────────────────────────────────────
# PR004 — "Which option should I choose?"
# Sections presenting two or more distinct
# options, paths, or protocols.
# Visual: Decision Tree or Comparison Table
# ─────────────────────────────────────────────

def _match_pr004(signals: dict) -> Optional[RuleResult]:
    branches = signals["conditional_branches"]
    has_comparison = signals.get("has_comparison", False)
    validation_gates = signals.get("validation_gate_branches", 0)
    choice_markers = signals.get("choice_option_markers", 0)

    # Need real branching, not just an "if" mention
    if branches < 2 and not has_comparison:
        return None

    # Exclude linear validation gates ("if successful, continue/click")
    # unless we also detect actual choice language.
    if branches >= 2 and not has_comparison and validation_gates >= 2 and choice_markers == 0:
        return None

    evidence = []
    boosts = []

    if branches >= 2:
        evidence.append(f"{branches} distinct conditional branches detected")
        boosts.append(15)

    if validation_gates >= 1:
        evidence.append(f"{validation_gates} validation-gate branch(es) detected")

    if has_comparison:
        evidence.append("Two named options being contrasted")
        boosts.append(10)

    # Prefer Decision Tree for if/else logic, Comparison Table for option lists
    if branches >= 2:
        visual = "Decision Tree"
        rationale = "Reader needs to trace conditions to the right choice without re-reading."
    else:
        visual = "Comparison Table"
        rationale = "Reader needs to evaluate options side-by-side before deciding."

    confidence = _confidence(65, boosts)
    priority = "High" if branches >= 3 or has_comparison else "Medium"

    return RuleResult(
        visual_type=visual,
        reader_question="Which option should I choose?",
        confidence=confidence,
        priority=priority,
        evidence=evidence,
        rationale=rationale,
    )


PR004 = Rule(
    id="PR004",
    reader_question="Which option should I choose?",
    visual_type="Decision Tree",
    description="Branching logic or option comparisons where readers must choose a path.",
    match=_match_pr004,
)


# ─────────────────────────────────────────────
# PR005 — "How are things connected?"
# Sections describing data flow or topology
# between named system components.
# Visual: Topology Diagram or Data Flow Diagram
# ─────────────────────────────────────────────

def _match_pr005(signals: dict) -> Optional[RuleResult]:
    rel = signals["relationship_count"]
    has_network = signals.get("has_network_nouns", False)
    steps = signals["steps"]

    # Need explicit relationships, not just component mentions
    if rel < 2:
        return None

    # If it's mostly a procedure, PR003 should win
    if steps >= 5 and rel < 3:
        return None

    evidence = [f"{rel} explicit component relationships detected"]
    boosts = []

    if has_network:
        boosts.append(15)
        evidence.append("Network/edge system vocabulary confirms topology context")

    if rel >= 3:
        boosts.append(10)
        evidence.append("3+ relationships — diagram prevents reader from losing track")

    # Three-way split: data flow > topology > architecture fallback.
    data_flow_score = signals.get("data_flow_verbs", 0)
    if data_flow_score >= 2:
        visual = "Data Flow Diagram"
        rationale = "Reader needs to trace data movement across components to understand the system."
        boosts.append(5)
        evidence.append(f"{data_flow_score} data transfer verbs detected")
    elif has_network:
        visual = "Topology Diagram"
        rationale = "Reader needs to see which components connect to which before configuring them."
    else:
        visual = "Architecture Diagram"
        rationale = "Reader needs a high-level structure view before moving into details."

    confidence = _confidence(60, boosts)
    priority = "High" if rel >= 3 and has_network else "Medium"

    return RuleResult(
        visual_type=visual,
        reader_question="How are things connected?",
        confidence=confidence,
        priority=priority,
        evidence=evidence,
        rationale=rationale,
    )


PR005 = Rule(
    id="PR005",
    reader_question="How are things connected?",
    visual_type="Topology Diagram",
    description="Data flow or network topology descriptions between named components.",
    match=_match_pr005,
)


# ─────────────────────────────────────────────
# Registry — ordered by priority
# Python rules run before JSON rules.
# ─────────────────────────────────────────────

PYTHON_RULES: list[Rule] = [PR001, PR002, PR003, PR004, PR005]
