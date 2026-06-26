"""
Reader-task-driven visual recommendation rules — v2

Pipeline position:

    Section Text
        │
        ▼
    Signal Extraction   ← compute_signals() in visual_detector.py
        │
        ▼
    Content Classification
        │
        ▼
    Worthiness Evaluation
        │
        ▼
    Reader Intent Detection  ← these rules
        │
        ▼
    Python Reasoning Rules
        │
        ▼
    Keyword Enhancement  ← visual_rules.json
        │
        ▼
    Conflict Resolution + Deduplication
        │
        ▼
    Gap Analysis
        │
        ▼
    Final Ranked Recommendations

Signal contract (all guaranteed by compute_signals()):

  Raw counts:
    steps                  int   — numbered/inferred procedural steps
    ui_interactions        int   — click/select/navigate/open/etc. hits
    relationship_count     int   — explicit A→B relationship sentences
    conditional_branches   int   — distinct if/else/otherwise branches
    word_count             int   — total words
    complexity_score       float — weighted step/nesting complexity
    step_lines             list  — extracted step text strings
    has_network_nouns      bool  — PLC/gateway/connector/hub/cloud present
    has_comparison         bool  — two named options contrasted
    action_verbs           int   — action-verb count
    verifications          int   — verify/validate/confirm hits
    warnings               int   — warning/caution/important hits
    data_flow_verbs        int   — sends/forwards/publishes/streams hits
    validation_gate_branches int — "if successful, continue" patterns
    choice_option_markers  int   — option/mode/versus/alternatively hits

  Density metrics (normalised per 100 words):
    ui_density             float — UI interactions / word_count × 100
    relationship_density   float — relationships / word_count × 100
    procedure_density      float — steps / word_count × 100
    decision_density       float — conditional_branches / word_count × 100

Confidence (0–100):
    Answers: "How certain am I this visual matches the content?"
    Computed via a named formula per rule.  Every number has a source.
    Formula pattern:
        confidence = base + Σ(named_component_scores) − Σ(named_penalties)

Priority (High / Medium / Low):
    Answers: "How much would the reader suffer without this visual?"
    Computed independently of confidence.
    High   = errors or significant confusion likely without it
    Medium = comprehension slows without it, but text is followable
    Low    = supplementary enhancement

Reader value (1–5):
    Answers: "How much effort does this visual save the reader?"
    5 = eliminates significant cognitive load (complex multi-system, long flow)
    4 = strong orientation benefit
    3 = moderate clarity improvement
    2 = nice-to-have
    1 = marginal benefit
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class RuleResult:
    visual_type: str
    reader_question: str    # The reader question this visual answers
    confidence: int         # 0–100: certainty this visual matches the content
    priority: str           # High/Medium/Low: urgency for the reader (independent of confidence)
    reader_value: int       # 1–5: effort saved for the reader
    evidence: list          # Human-readable signal explanations shown in the UI
    rationale: str          # One sentence why this visual helps
    source: str = "python"


@dataclass
class Rule:
    id: str
    reader_question: str
    visual_type: str
    description: str
    match: Callable         # (signals: dict) -> Optional[RuleResult]


# ─────────────────────────────────────────────
# Confidence formula helper
# ─────────────────────────────────────────────

def _formula_confidence(base: int, components: dict, penalties: dict | None = None) -> int:
    """
    Compute confidence from named, bounded formula components.
    All keys name exactly what they contribute and why.
    """
    total = base + sum(components.values())
    if penalties:
        total -= sum(penalties.values())
    return max(0, min(100, total))


# ─────────────────────────────────────────────
# PR_CONNECTIONS — merged PR001 + PR005
# "How are components related?"
#
# Covers both high-level architecture overviews
# and detailed topology/data-flow descriptions.
# Eliminates the previous overlap where PR001 and
# PR005 competed on the same sections.
#
# Visual output hierarchy (mutually exclusive):
#   data_flow_verbs ≥ 2  →  Data Flow Diagram
#   has_network_nouns and rel ≥ 2  →  Topology Diagram
#   otherwise  →  Architecture Diagram
#
# Confidence formula (all components named and bounded):
#   base                 = 20  (minimum if gate passes)
#   relationship_score   = rel × 10,          cap 30   (each A→B sentence = 10)
#   density_score        = rel_density × 20,  cap 20   (relationships per 100 words)
#   network_score        = 20 if network nouns present, else 0
#   dataflow_score       = data_flow_verbs × 5, cap 15 (transfer verbs = specificity)
#
# Priority (independent of confidence):
#   High   = 3+ relationships AND network nouns: reader will misconfigure without map
#   Medium = 2+ relationships or 1 + network vocabulary
#   Low    = single weak relationship
#
# Reader value (1–5):
#   5 = complex multi-system data pipeline
#   4 = multi-component system with network vocabulary
#   3 = two-component relationship
#   2 = single weak relationship mention
# ─────────────────────────────────────────────

def _match_pr_connections(signals: dict) -> Optional[RuleResult]:
    rel = signals["relationship_count"]
    data_flow = signals.get("data_flow_verbs", 0)
    has_network = signals.get("has_network_nouns", False)
    steps = signals["steps"]
    rel_density = signals.get("relationship_density", 0.0)

    # Required gate: at least one explicit relationship sentence.
    if rel < 1:
        return None

    # If section is predominantly procedural and relationships are sparse,
    # PR_WORKFLOW wins — avoid overlap.
    if steps >= 5 and rel < 2:
        return None

    # Formula components (named, bounded):
    components = {
        "relationship_score": min(30, rel * 10),            # 0–30: each rel = 10pts
        "density_score":      min(20, int(rel_density * 20)), # 0–20: rels per 100 words
        "network_score":      20 if has_network else 0,      # 0–20: domain vocabulary
        "dataflow_score":     min(15, data_flow * 5),        # 0–15: transfer verb count
    }
    confidence = _formula_confidence(base=20, components=components)

    # Visual type hierarchy (Data Flow > Topology > Architecture):
    if data_flow >= 2:
        visual = "Data Flow Diagram"
        rationale = "Reader needs to trace data movement across components to understand the system."
    elif has_network and rel >= 2:
        visual = "Topology Diagram"
        rationale = "Reader needs to see which components connect to which before configuring them."
    else:
        visual = "Architecture Diagram"
        rationale = "Reader needs a high-level structure view before moving into details."

    # Priority — how much would the reader suffer without this visual?
    if rel >= 3 and has_network:
        priority = "High"
    elif rel >= 2 or (rel >= 1 and has_network):
        priority = "Medium"
    else:
        priority = "Low"

    # Reader value — effort saved following this section
    if rel >= 3 and has_network and data_flow >= 1:
        reader_value = 5
    elif rel >= 3 or (rel >= 2 and has_network):
        reader_value = 4
    elif rel >= 2:
        reader_value = 3
    else:
        reader_value = 2

    evidence = [f"{rel} explicit component relationship(s) found"]
    if has_network:
        evidence.append("Network/edge vocabulary detected (PLC, gateway, cloud…)")
    if data_flow >= 1:
        evidence.append(f"{data_flow} data-transfer verb(s) detected (sends, forwards, publishes…)")
    if rel_density >= 1.0:
        evidence.append(f"Relationship density: {rel_density:.1f} per 100 words")

    return RuleResult(
        visual_type=visual,
        reader_question="How are components related?",
        confidence=confidence,
        priority=priority,
        reader_value=reader_value,
        evidence=evidence,
        rationale=rationale,
    )


PR_CONNECTIONS = Rule(
    id="PR_CONNECTIONS",
    reader_question="How are components related?",
    visual_type="Architecture / Topology / Data Flow Diagram",
    description="Overview and topology sections describing relationships between system components.",
    match=_match_pr_connections,
)


# ─────────────────────────────────────────────
# PR_SCREENSHOT — "Where do I click?"
# Dense UI interaction sequences.
# Visual: Screenshot
#
# Confidence formula:
#   base               = 25
#   ui_density_score   = ui_density × 8,         cap 45  (interactions per 100 words × 8)
#   step_coverage      = steps × 3,               cap 20  (each step = 3pts)
#   checkpoint_score   = verifications × 5,       cap 10  (each verify = 5pts)
#
# Gate: ui_density ≥ 2.0 (at least 2 UI actions per 100 words)
# ─────────────────────────────────────────────

def _match_pr_screenshot(signals: dict) -> Optional[RuleResult]:
    ui = signals["ui_interactions"]
    ui_density = signals.get("ui_density", 0.0)
    steps = signals["steps"]

    # Required gate: meaningful UI interaction density
    if ui_density < 2.0:
        return None

    # Hard block: trivially simple single instruction
    if steps <= 1 and ui_density < 3.0 and signals["word_count"] < 25:
        return None

    # Formula components (named, bounded):
    components = {
        "ui_density_score": min(45, int(ui_density * 8)),                       # 0–45: primary signal
        "step_coverage":    min(20, steps * 3),                                  # 0–20: each step = 3
        "checkpoint_score": min(10, signals.get("verifications", 0) * 5),       # 0–10: verify = 5
    }
    confidence = _formula_confidence(base=25, components=components)

    # Priority — would reader click wrong things without this?
    if steps >= 5 and ui >= 6:
        priority = "High"
    elif ui >= 3:
        priority = "Medium"
    else:
        priority = "Low"

    # Reader value — effort saved navigating complex UI
    if steps >= 7 and ui_density >= 4.0:
        reader_value = 5
    elif steps >= 4 or ui_density >= 3.0:
        reader_value = 4
    elif ui_density >= 2.0:
        reader_value = 3
    else:
        reader_value = 2

    evidence = [f"UI density: {ui_density:.1f} interactions per 100 words ({ui} total)"]
    if steps >= 3:
        evidence.append(f"{steps} procedural steps guide user through the UI")
    if signals.get("verifications", 0) >= 1:
        evidence.append("Verification step detected — screenshot confirms expected state")

    return RuleResult(
        visual_type="Screenshot",
        reader_question="Where do I click?",
        confidence=confidence,
        priority=priority,
        reader_value=reader_value,
        evidence=evidence,
        rationale="Reader needs to see the exact UI state to navigate confidently.",
    )


PR_SCREENSHOT = Rule(
    id="PR_SCREENSHOT",
    reader_question="Where do I click?",
    visual_type="Screenshot",
    description="UI navigation sequences where readers need to see the interface state.",
    match=_match_pr_screenshot,
)


# ─────────────────────────────────────────────
# PR_WORKFLOW — "What happens next?"
# Multi-step sequential procedures.
# Visual: Workflow Diagram
#
# Confidence formula:
#   base                 = 20
#   procedure_depth      = steps × 4,                          cap 40
#   complexity_bonus     = min(complexity_score, 8) × 2,       cap 16
#   safety_signal        = warnings × 5 + verifications × 3,   cap 15
#   density_bonus        = procedure_density × 3,               cap 10
#
# Gate: steps ≥ 4
# ─────────────────────────────────────────────

def _match_pr_workflow(signals: dict) -> Optional[RuleResult]:
    steps = signals["steps"]
    complexity = signals["complexity_score"]
    procedure_density = signals.get("procedure_density", 0.0)

    # Required gate: meaningful sequence
    if steps < 4:
        return None

    # Formula components (named, bounded):
    components = {
        "procedure_depth":  min(40, steps * 4),
        "complexity_bonus": min(16, int(min(complexity, 8) * 2)),
        "safety_signal":    min(15, signals.get("warnings", 0) * 5
                               + signals.get("verifications", 0) * 3),
        "density_bonus":    min(10, int(procedure_density * 3)),
    }
    confidence = _formula_confidence(base=20, components=components)

    # Priority — would reader lose their place without a visual?
    if steps >= 7 or (steps >= 5 and signals.get("warnings", 0) >= 1):
        priority = "High"
    elif steps >= 5:
        priority = "Medium"
    else:
        priority = "Low"

    # Reader value — effort saved tracking a multi-step process
    if steps >= 10:
        reader_value = 5
    elif steps >= 7 or complexity >= 8:
        reader_value = 4
    elif steps >= 5:
        reader_value = 3
    else:
        reader_value = 2

    evidence = [f"{steps} procedural steps detected"]
    if steps >= 7:
        evidence.append("Long procedure — workflow diagram reduces cognitive load")
    elif steps >= 5:
        evidence.append("Medium-length procedure benefits from a visual sequence")
    if complexity >= 8:
        evidence.append(f"Complexity score {complexity:.1f} — nested or parallel steps detected")
    if signals.get("verifications", 0) >= 2:
        evidence.append(f"{signals['verifications']} verification checkpoints — sequence must be visible")
    if signals.get("warnings", 0) >= 1:
        evidence.append("Warning present — reader must not skip steps")

    return RuleResult(
        visual_type="Workflow Diagram",
        reader_question="What happens next?",
        confidence=confidence,
        priority=priority,
        reader_value=reader_value,
        evidence=evidence,
        rationale="Reader needs to see the full sequence to understand where they are in the process.",
    )


PR_WORKFLOW = Rule(
    id="PR_WORKFLOW",
    reader_question="What happens next?",
    visual_type="Workflow Diagram",
    description="Multi-step procedures where sequence and completeness matter to the reader.",
    match=_match_pr_workflow,
)


# ─────────────────────────────────────────────
# PR_DECISION — "Which option should I choose?"
# Branching logic or option comparisons.
# Visual: Decision Tree or Comparison Table
#
# Confidence formula:
#   base                 = 30
#   branch_score         = conditional_branches × 8,  cap 32
#   comparison_bonus     = 20 if named options contrasted, else 0
#   choice_marker_score  = choice_option_markers × 2, cap 10
# Penalty:
#   gate_penalty         = validation_gates × 5,       cap 20
#     (linear "if successful" gates reduce confidence because
#      they are not real decision points for the reader)
#
# Gate: branches ≥ 2 OR has_comparison
# Suppression: if all branches are validation gates and no choice
#              language present → blocked entirely
# ─────────────────────────────────────────────

def _match_pr_decision(signals: dict) -> Optional[RuleResult]:
    branches = signals["conditional_branches"]
    has_comparison = signals.get("has_comparison", False)
    validation_gates = signals.get("validation_gate_branches", 0)
    choice_markers = signals.get("choice_option_markers", 0)

    # Required gate
    if branches < 2 and not has_comparison:
        return None

    # Suppress linear validation gates unless explicit choice language present
    if branches >= 2 and not has_comparison and validation_gates >= 2 and choice_markers == 0:
        return None

    # Formula components (named, bounded):
    components = {
        "branch_score":        min(32, branches * 8),           # 0–32: each branch = 8pts
        "comparison_bonus":    20 if has_comparison else 0,      # 0–20: named option contrast
        "choice_marker_score": min(10, choice_markers * 2),      # 0–10: option vocabulary
    }
    # Partial penalty: validation gates dilute real decision-point signal
    penalties = {
        "gate_penalty": min(20, validation_gates * 5),
    }
    confidence = _formula_confidence(base=30, components=components, penalties=penalties)

    # Visual selection: Decision Tree for if/else logic, Comparison Table for option contrast
    if branches >= 2:
        visual = "Decision Tree"
        rationale = "Reader needs to trace conditions to the right outcome without re-reading."
    else:
        visual = "Comparison Table"
        rationale = "Reader needs to evaluate options side-by-side before choosing."

    # Priority — wrong choice can cause errors or rework
    if branches >= 3 or (branches >= 2 and has_comparison):
        priority = "High"
    elif has_comparison:
        priority = "Medium"
    else:
        priority = "Low"

    # Reader value — effort saved navigating branching logic
    if branches >= 4:
        reader_value = 5
    elif branches >= 3 or (branches >= 2 and has_comparison):
        reader_value = 4
    elif branches >= 2:
        reader_value = 3
    else:
        reader_value = 2

    evidence = []
    if branches >= 2:
        evidence.append(f"{branches} conditional branches detected")
    if has_comparison:
        evidence.append("Two named options contrasted (vs / 'use X for Y, use Z for W')")
    if choice_markers >= 2:
        evidence.append("Choice vocabulary detected: option/mode/versus/alternatively…")
    if validation_gates >= 1:
        evidence.append(f"Note: {validation_gates} validation gate(s) detected — not decision points")

    return RuleResult(
        visual_type=visual,
        reader_question="Which option should I choose?",
        confidence=confidence,
        priority=priority,
        reader_value=reader_value,
        evidence=evidence,
        rationale=rationale,
    )


PR_DECISION = Rule(
    id="PR_DECISION",
    reader_question="Which option should I choose?",
    visual_type="Decision Tree",
    description="Branching logic or option comparisons where readers must choose a path.",
    match=_match_pr_decision,
)


# ─────────────────────────────────────────────
# Registry — execution order matters.
# PR_CONNECTIONS first so topology sections are
# claimed before PR_WORKFLOW can over-reach.
# Python rules run before JSON keyword rules.
#
# Renamed from v1:
#   PR001 + PR005  →  PR_CONNECTIONS  (merged)
#   PR002          →  PR_SCREENSHOT
#   PR003          →  PR_WORKFLOW
#   PR004          →  PR_DECISION
# ─────────────────────────────────────────────

PYTHON_RULES: list[Rule] = [PR_CONNECTIONS, PR_SCREENSHOT, PR_WORKFLOW, PR_DECISION]
