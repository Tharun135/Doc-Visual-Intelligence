import json
import re


with open("rules/visual_rules.json", "r", encoding="utf-8") as file:
    rules = json.load(file)

with open("rules/knowledge_model.json", "r", encoding="utf-8") as file:
    knowledge_model = json.load(file)


ACTION_VERBS = {
    "open", "click", "select", "choose", "validate", "start", "verify",
    "check", "configure", "deploy", "save", "run", "import", "export",
    "upload", "download", "add", "remove", "connect", "set", "enter",
    "create", "transform", "return", "complete"
}

CHECKPOINT_TERMS = {
    "validate", "verify", "confirm", "review", "save", "apply", "test", "status"
}

UI_INTERACTION_TERMS = {
    "open", "click", "select", "choose", "enter", "upload", "download", "navigate",
    "set", "configure", "connect", "import", "export", "save", "apply"
}

SCREENSHOT_TYPES = {"Screenshot", "Configuration Screenshot"}
DIAGRAM_TYPES = {
    "Topology Diagram",
    "Architecture Diagram",
    "Data Flow Diagram",
    "Workflow Diagram",
    "Flowchart",
    "Sequence Diagram",
    "Decision Tree",
    "Before/After Comparison",
    "Mapping Table"
}

GIF_TYPES = {"GIF Tutorial"}
RELATIONSHIP_REQUIRED_VISUALS = {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram"}

RELATION_PATTERNS = [
    (r"(?P<src>.+?)\s+sends\s+(?:data\s+)?to\s+(?P<dst>.+)", "sends"),
    (r"(?P<src>.+?)\s+publishes\s+(?:data\s+)?to\s+(?P<dst>.+)", "publishes"),
    (r"(?P<src>.+?)\s+communicates\s+with\s+(?P<dst>.+)", "communicates with"),
    (r"(?P<src>.+?)\s+connects\s+(?:directly\s+)?to\s+(?P<dst>.+)", "connects to"),
    (r"(?P<src>.+?)\s+deploys\s+to\s+(?P<dst>.+)", "deploys to"),
    (r"(?P<src>.+?)\s+transfers\s+(?:data\s+)?to\s+(?P<dst>.+)", "transfers to"),
    (r"(?P<src>.+?)\s+forwards\s+(?:data\s+)?to\s+(?P<dst>.+)", "forwards"),
    (r"(?P<src>.+?)\s+routes\s+(?:data\s+)?to\s+(?P<dst>.+)", "routes to"),
    (r"(?P<src>.+?)\s+passes\s+(?:data\s+)?to\s+(?P<dst>.+)", "passes to")
]


def _count_pattern(content, pattern):
    return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))


def extract_procedure_steps(content):
    numbered = re.findall(r"^\s*(?:\d+[\.)]|step\s+\d+)\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
    if numbered:
        return [step.strip() for step in numbered if step.strip()]

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    inferred = []
    for line in lines:
        first_word = re.sub(r"[^a-zA-Z]", "", line.split()[0]).lower() if line.split() else ""
        if first_word in ACTION_VERBS:
            inferred.append(line)
    return inferred


def _sanitize_diagram_label(label):
    sanitized = re.sub(r"\s+", " ", label.strip())
    sanitized = sanitized.strip(" -:;,.()[]{}")
    return sanitized.replace('"', "'")


def _clean_component_label(text):
    label = _sanitize_diagram_label(text)
    label = re.sub(r"^(the|a|an)\s+", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\b(?:data|messages?|traffic|requests?)$", "", label, flags=re.IGNORECASE).strip()
    return label


def _split_content_sentences(content):
    fragments = []
    for block in content.splitlines():
        line = block.strip()
        if not line:
            continue
        pieces = re.split(r"(?<=[.!?])\s+", line)
        for piece in pieces:
            candidate = piece.strip()
            if candidate:
                fragments.append(candidate)
    return fragments


def _build_node_id(index):
    return f"N{index + 1}"


def _resolve_component_reference(label, known_labels):
    lowered = label.lower()
    for existing in reversed(known_labels):
        existing_lower = existing.lower()
        if existing_lower == lowered:
            return existing
        if existing_lower.endswith(f" {lowered}"):
            return existing
    return label


def extract_relationship_statements(content):
    relationships = []
    seen = set()

    for sentence in _split_content_sentences(content):
        cleaned_sentence = sentence.strip().strip(".")
        for pattern, label in RELATION_PATTERNS:
            match = re.match(pattern, cleaned_sentence, re.IGNORECASE)
            if not match:
                continue

            src = _clean_component_label(match.group("src"))
            dst = _clean_component_label(match.group("dst"))
            if not src or not dst or src.lower() == dst.lower():
                continue

            key = (src.lower(), label, dst.lower())
            if key in seen:
                continue

            seen.add(key)
            relationships.append({
                "source": src,
                "label": label,
                "target": dst
            })
            break

    return relationships


def extract_decision_logic(content):
    """Extract if/then/else logic from content using multiple patterns."""
    normalized = re.sub(r"\s+", " ", content).strip()
    
    # Pattern 1: "if ..., ... . otherwise/else, ..."
    match = re.search(
        r"if\s+(?P<condition>[^,.]+),\s*(?P<yes>[^.]+)\.\s*(?:otherwise|else)\s*,?\s*(?P<no>[^.]+)",
        normalized,
        re.IGNORECASE
    )
    if match:
        return {
            "condition": _sanitize_diagram_label(match.group("condition")),
            "yes_action": _sanitize_diagram_label(match.group("yes")),
            "no_action": _sanitize_diagram_label(match.group("no"))
        }
    
    # Pattern 2: Multi-line if/else with numbered bullets
    # "2. If ... : ... 3. If ... : ..."
    if_matches = re.findall(
        r"if\s+([^:]+):\s*([^.]+)\.",
        normalized,
        re.IGNORECASE
    )
    if len(if_matches) >= 2:
        # Take first as success, second as failure
        condition, yes_action = if_matches[0]
        _, no_action = if_matches[1]
        return {
            "condition": _sanitize_diagram_label(condition.strip()),
            "yes_action": _sanitize_diagram_label(yes_action.strip()),
            "no_action": _sanitize_diagram_label(no_action.strip())
        }
    
    # Pattern 3: "succeeds" vs "fails" keywords
    if re.search(r"succeed|success", normalized, re.IGNORECASE) and \
       re.search(r"fail|error", normalized, re.IGNORECASE):
        # Extract the test/check action
        check_match = re.search(r"(test|check|verify)\s+([^.]+)\.", normalized, re.IGNORECASE)
        if check_match:
            check_action = check_match.group(2).strip()
            # Extract success and failure outcomes
            success = re.search(r"(?:if|when)\s+(?:it\s+)?succeed[s]?[^.]*:\s*([^.]+)", normalized, re.IGNORECASE)
            failure = re.search(r"(?:if|when|otherwise)\s+(?:it\s+)?fail[s]?[^.]*:\s*([^.]+)", normalized, re.IGNORECASE)
            
            if success and failure:
                return {
                    "condition": _sanitize_diagram_label(check_action),
                    "yes_action": _sanitize_diagram_label(success.group(1).strip()),
                    "no_action": _sanitize_diagram_label(failure.group(1).strip())
                }
    
    return None


def extract_troubleshooting_cases(content):
    cases = []
    pattern = re.compile(r"Error\s+([A-Za-z0-9_-]+)\s*:\s*(.+?)(?=(?:\n\s*Error\s+[A-Za-z0-9_-]+\s*:)|\Z)", re.IGNORECASE | re.DOTALL)
    for code, resolution in pattern.findall(content):
        lines = [line.strip() for line in resolution.splitlines() if line.strip()]
        summary = _sanitize_diagram_label(lines[0]) if lines else "Review troubleshooting guidance"
        cases.append({
            "code": code,
            "resolution": summary
        })
    return cases


def build_workflow_artifact(title, signals):
    steps = signals.get("step_lines", [])
    if len(steps) < 2:
        return None

    mermaid_lines = ["flowchart TD"]
    plantuml_lines = ["@startuml", "start"]
    node_ids = []

    for index, step in enumerate(steps):
        node_id = _build_node_id(index)
        node_ids.append(node_id)
        label = _sanitize_diagram_label(step)
        mermaid_lines.append(f'{node_id}["{ label}"]')
        plantuml_lines.append(f':{label};')

    # Create individual arrows between steps (not a single flat chain)
    for i in range(len(node_ids) - 1):
        mermaid_lines.append(f"{node_ids[i]} --> {node_ids[i+1]}")
    
    plantuml_lines.extend(["stop", "@enduml"])

    return {
        "artifact_type": "workflow",
        "title": title,
        "mermaid": "\n".join(mermaid_lines),
        "plantuml": "\n".join(plantuml_lines),
        "summary": f"Generated from {len(steps)} procedural steps in the uploaded section."
    }


def build_relationship_artifact(title, content, direction="LR"):
    relationships = extract_relationship_statements(content)

    if not relationships:
        nodes = extract_entities(content)
        fallback_relationships = extract_relationships(nodes)
        if len(fallback_relationships) < 1:
            return None
        relationships = [
            {"source": src, "label": "connects to", "target": dst}
            for src, dst in fallback_relationships
        ]

    resolved_labels = []
    normalized_relationships = []
    for relation in relationships:
        src = _resolve_component_reference(relation["source"], resolved_labels)
        dst = _resolve_component_reference(relation["target"], resolved_labels)
        normalized_relationships.append({
            "source": src,
            "label": relation["label"],
            "target": dst
        })
        if src not in resolved_labels:
            resolved_labels.append(src)
        if dst not in resolved_labels:
            resolved_labels.append(dst)

    relationships = normalized_relationships

    mermaid_lines = [f"graph {direction}"]
    plantuml_lines = ["@startuml", "left to right direction"]
    alias_map = {}
    node_order = []

    def ensure_alias(label):
        if label not in alias_map:
            alias = _build_node_id(len(alias_map))
            alias_map[label] = alias
            node_order.append(label)
        return alias_map[label]

    for relation in relationships:
        src = relation["source"]
        dst = relation["target"]
        label = relation["label"]
        src_id = ensure_alias(src)
        dst_id = ensure_alias(dst)
        mermaid_lines.append(f'{src_id}["{_sanitize_diagram_label(src)}"] -->|{label}| {dst_id}["{_sanitize_diagram_label(dst)}"]')

    for label in node_order:
        alias = alias_map[label]
        plantuml_lines.append(f'component "{_sanitize_diagram_label(label)}" as {alias}')

    for relation in relationships:
        plantuml_lines.append(
            f'{alias_map[relation["source"]]} --> {alias_map[relation["target"]]} : {relation["label"]}'
        )

    plantuml_lines.append("@enduml")

    return {
        "artifact_type": "relationship",
        "title": title,
        "nodes": node_order,
        "relationships": [f'{item["source"]} --{item["label"]}--> {item["target"]}' for item in relationships],
        "mermaid": "\n".join(mermaid_lines),
        "plantuml": "\n".join(plantuml_lines),
        "summary": f"Generated from {len(relationships)} relationships extracted from the uploaded content."
    }


def build_decision_artifact(title, content):
    decision = extract_decision_logic(content)
    if not decision:
        return None

    condition = decision["condition"]
    yes_action = decision["yes_action"]
    no_action = decision["no_action"]

    mermaid_lines = [
        "flowchart TD",
        'N1["Evaluate Condition"]',
        f'N2{{"{condition}?"}}',
        f'N3["{yes_action}"]',
        f'N4["{no_action}"]',
        "N1 --> N2",
        "N2 -->|Yes| N3",
        "N2 -->|No| N4"
    ]

    plantuml_lines = [
        "@startuml",
        "start",
        ":Evaluate Condition;",
        f'if ({condition}?) then (Yes)',
        f'  :{yes_action};',
        "else (No)",
        f'  :{no_action};',
        "endif",
        "stop",
        "@enduml"
    ]

    return {
        "artifact_type": "decision",
        "title": title,
        "mermaid": "\n".join(mermaid_lines),
        "plantuml": "\n".join(plantuml_lines),
        "summary": "Generated from explicit if/otherwise logic in the uploaded content."
    }


def build_troubleshooting_artifact(title, content):
    cases = extract_troubleshooting_cases(content)
    if not cases:
        return None

    mermaid_lines = ["flowchart TD", 'N0["Troubleshooting Entry"]']
    plantuml_lines = ["@startuml", "left to right direction", 'rectangle "Troubleshooting Entry" as N0']

    for index, case in enumerate(cases, start=1):
        error_id = f"E{index}"
        action_id = f"R{index}"
        error_label = f'Error {case["code"]}'
        resolution_label = case["resolution"]
        mermaid_lines.extend([
            f'{error_id}["{error_label}"]',
            f'{action_id}["{resolution_label}"]',
            f'N0 --> {error_id}',
            f'{error_id} --> {action_id}'
        ])
        plantuml_lines.extend([
            f'rectangle "{error_label}" as {error_id}',
            f'rectangle "{resolution_label}" as {action_id}',
            f'N0 --> {error_id}',
            f'{error_id} --> {action_id}'
        ])

    plantuml_lines.append("@enduml")

    return {
        "artifact_type": "troubleshooting",
        "title": title,
        "mermaid": "\n".join(mermaid_lines),
        "plantuml": "\n".join(plantuml_lines),
        "summary": f"Generated from {len(cases)} troubleshooting cases found in the uploaded content."
    }


def build_generated_artifact(visual_type, title, content, signals, content_type):
    if content_type == "Troubleshooting":
        troubleshooting_artifact = build_troubleshooting_artifact(title, content)
        if troubleshooting_artifact:
            return troubleshooting_artifact

    if visual_type in {"Workflow Diagram", "Sequence Diagram"}:
        return build_workflow_artifact(title, signals)

    if visual_type in {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram"}:
        return build_relationship_artifact(title, content, direction="LR")

    if visual_type in {"Decision Tree", "Flowchart"}:
        return build_decision_artifact(title, content) or build_workflow_artifact(title, signals)

    return None


def compute_signals(content):
    step_lines = extract_procedure_steps(content)
    numbered_steps = _count_pattern(content, r"^\s*(?:\d+[\.)]|step\s+\d+)")
    nested_steps = _count_pattern(content, r"^\s{2,}(?:[-*]|[a-z][\.)])")
    warnings = _count_pattern(content, r"\b(warning|caution|important|notice)\b")
    notes = _count_pattern(content, r"\b(note|tip|hint)\b")
    prerequisites = _count_pattern(content, r"\b(prerequisite|requirement|before you begin|precondition)\b")
    verifications = _count_pattern(content, r"\b(verify|validation|validate|check status|confirm)\b")
    ui_interactions = _count_pattern(content, r"\b(click|select|menu|dialog|tab|button|panel)\b")
    action_verbs = _count_pattern(content, r"\b(open|click|select|choose|validate|start|verify|check|configure|deploy|save|run|import|export|upload|download|add|remove|connect|set|enter|create|transform|return|complete)\b")
    word_count = len(content.split())

    complexity_score = (
        len(step_lines)
        + nested_steps * 1.5
        + warnings * 1.5
        + notes * 0.5
        + prerequisites
        + verifications * 1.2
    )

    return {
        "step_lines": step_lines,
        "steps": len(step_lines),
        "numbered_steps": numbered_steps,
        "nested_steps": nested_steps,
        "warnings": warnings,
        "notes": notes,
        "prerequisites": prerequisites,
        "verifications": verifications,
        "ui_interactions": ui_interactions,
        "action_verbs": action_verbs,
        "word_count": word_count,
        "complexity_score": round(complexity_score, 1)
    }


def get_confidence_category(confidence):
    """Convert numeric confidence (0-100) to categorical (Low/Medium/High)."""
    if confidence >= 80:
        return "High"
    elif confidence >= 50:
        return "Medium"
    else:
        return "Low"


def classify_content(title, content, signals):
    title_lower = title.lower()
    content_lower = content.lower()
    combined = title_lower + " " + content_lower

    classifications = []

    troubleshoot_match = len(re.findall(r"\b(troubleshoot|error|failure|issue|fault)\b", combined))
    if troubleshoot_match > 0:
        classifications.append(("Troubleshooting", min(90, 60 + troubleshoot_match * 10)))

    if signals["steps"] >= 3 or re.search(r"\b(procedure|steps|how to)\b", title_lower):
        procedure_confidence = 95 if signals["steps"] >= 5 else (85 if signals["steps"] >= 3 else 70)
        classifications.append(("Procedure", procedure_confidence))
    elif signals["action_verbs"] >= 3:
        classifications.append(("Procedure", 75))
    elif signals["steps"] >= 1:  # If at least 1 step detected, lean toward Procedure
        classifications.append(("Procedure", 65))

    arch_match = len(re.findall(r"\b(topology|architecture|system layout|network|integration)\b", combined))
    if arch_match > 0:
        classifications.append(("Architecture", min(90, 60 + arch_match * 15)))

    if re.search(r"\b(parameter|field|property|reference|api|table)\b", combined):
        classifications.append(("Reference", 80))

    if not classifications:
        return ("Concept", 50)

    best = max(classifications, key=lambda x: x[1])
    return best


def complexity_recommendation(signals):
    steps = signals["steps"]
    if steps < 3:
        return "No visual"
    if steps <= 5:
        return "Screenshot"
    if steps <= 10:
        return "Workflow Diagram"
    return "GIF Tutorial"


def build_priority(confidence, signals):
    if confidence >= 85 or signals["complexity_score"] >= 9:
        return "High"
    if confidence >= 65 or signals["complexity_score"] >= 5:
        return "Medium"
    return "Low"


def select_final_recommendations(candidates, signals, content_type):
    if not candidates:
        return []

    ranked = sorted(candidates, key=lambda item: (item["confidence"], item["score"]), reverse=True)

    # For overview-style concept/reference sections, return a single best visual.
    if content_type in {"Concept", "Reference"} and signals["steps"] <= 2 and signals["complexity_score"] <= 5:
        return ranked[:1]

    # If confidence drops sharply after the first recommendation, keep only the primary one.
    if len(ranked) >= 2 and ranked[0]["confidence"] - ranked[1]["confidence"] >= 20:
        return ranked[:1]

    return ranked[:3]


def _keyword_hits(content_lower, keyword):
    keyword_lower = keyword.lower()
    if " " in keyword_lower:
        return 1 if keyword_lower in content_lower else 0
    return len(re.findall(r"\b" + re.escape(keyword_lower) + r"\b", content_lower))


def detect_existing_visual_assets(content):
    markdown_images = _count_pattern(content, r"!\[[^\]]*\]\([^\)]+\)")
    html_images = _count_pattern(content, r"<img\b")
    screenshot_mentions = _count_pattern(content, r"\b(screenshot|screen capture|figure)\b")
    diagram_mentions = _count_pattern(content, r"\b(diagram|topology|architecture|flowchart|sequence)\b")
    gif_mentions = _count_pattern(content, r"\b(gif|animation|video demo)\b")

    screenshot_count = markdown_images + html_images + screenshot_mentions
    diagram_count = diagram_mentions
    gif_count = gif_mentions

    return {
        "screenshot": screenshot_count,
        "diagram": diagram_count,
        "gif": gif_count,
        "total": screenshot_count + diagram_count + gif_count
    }


def suggest_screenshot_placement(signals):
    steps = signals["step_lines"]
    if not steps:
        return None

    # Screenshot guidance is strongest immediately after a concrete UI interaction.
    for index, step in enumerate(steps):
        step_lower = step.lower()
        if any(term in step_lower for term in UI_INTERACTION_TERMS):
            step_truncated = step[:60]
            return {
                "placement": "after_step",
                "step_number": index + 1,
                "step_text": step_truncated,
                "display_text": f"After step {index + 1}: {step_truncated}",
                "reason": "UI interaction step detected where visual confirmation is most useful"
            }

    # Place visuals where users need a confidence checkpoint (validation/verification/save).
    for index, step in enumerate(steps):
        step_lower = step.lower()
        if any(term in step_lower for term in CHECKPOINT_TERMS):
            step_truncated = step[:60]
            return {
                "placement": "after_step",
                "step_number": index + 1,
                "step_text": step_truncated,
                "display_text": f"After step {index + 1}: {step_truncated}",
                "reason": "Checkpoint step detected where users need confirmation"
            }

    middle = max(1, len(steps) // 2)
    step_truncated = steps[middle - 1][:60]
    return {
        "placement": "after_step",
        "step_number": middle,
        "step_text": step_truncated,
        "display_text": f"After step {middle}: {step_truncated}",
        "reason": "Mid-workflow placement provides orientation in long procedures"
    }


def suggest_diagram_placement(visual_type, content_type):
    if visual_type in DIAGRAM_TYPES and content_type in {"Concept", "Architecture", "Reference", "Procedure"}:
        return {
            "placement": "before_section",
            "step_number": 0,
            "display_text": "Before the procedure steps (context first)",
            "reason": "Diagram provides system context before users start the workflow"
        }
    return None


def suggest_visual_placement(visual_type, content_type, signals):
    if visual_type in SCREENSHOT_TYPES.union(GIF_TYPES):
        return suggest_screenshot_placement(signals)

    return suggest_diagram_placement(visual_type, content_type)


def _normalize_node_id(label):
    return re.sub(r"[^a-zA-Z0-9]", "", label) or "Node"


def extract_entities(content):
    content_lower = content.lower()
    entities = []
    seen = set()
    entities_cfg = knowledge_model.get("entities", {})
    for canonical, metadata in entities_cfg.items():
        aliases = metadata.get("aliases", [])
        for alias in aliases:
            pattern = r"\b" + re.escape(alias.lower()) + r"\b"
            if re.search(pattern, content_lower):
                if canonical not in seen:
                    entities.append(canonical)
                    seen.add(canonical)
                break
    return entities


def extract_relationships(entities):
    known = set(entities)
    relations_cfg = knowledge_model.get("relationships", [])
    relationships = []
    for relation in relations_cfg:
        if len(relation) != 2:
            continue
        src, dst = relation
        if src in known and dst in known:
            relationships.append((src, dst))

    if relationships:
        return relationships

    ordered = list(entities)
    fallback = []
    for index in range(len(ordered) - 1):
        fallback.append((ordered[index], ordered[index + 1]))
    return fallback


def build_diagram_blueprint(content):
    artifact = build_relationship_artifact("Diagram Blueprint", content, direction="LR")
    if not artifact:
        return None

    return {
        "nodes": artifact.get("nodes", []),
        "relationships": artifact.get("relationships", []),
        "mermaid": artifact["mermaid"]
    }


def map_visual_family(visual_type):
    if visual_type in SCREENSHOT_TYPES:
        return "screenshot"
    if visual_type in GIF_TYPES:
        return "gif"
    if visual_type in DIAGRAM_TYPES:
        return "diagram"
    return None


def apply_gap_analysis(visual_type, existing_assets):
    family = map_visual_family(visual_type)
    if not family:
        return {
            "family": "other",
            "existing_count": 0,
            "required_count": 1,
            "gap_message": "Evaluate manually",
            "coverage_display": "Coverage: 0/1 visuals (0%)"
        }

    existing_count = existing_assets.get(family, 0)
    required_count = 1

    if existing_count >= required_count:
        gap_message = "No additional visuals needed"
    else:
        gap_message = "Additional visual recommended"

    coverage_pct = int((existing_count / required_count * 100)) if required_count > 0 else 0
    return {
        "family": family,
        "existing_count": existing_count,
        "required_count": required_count,
        "gap_message": gap_message,
        "coverage_display": f"Coverage: {existing_count}/{required_count} visuals ({coverage_pct}%)"
    }


def build_visual_package(recommendations, signals, content_type):
    # Exclude already-covered visual types from package composition.
    filtered = [
        item for item in recommendations
        if item["visual_type"] != "No recommendation"
        and item["confidence"] >= 45
        and item.get("gap_message") != "No additional visuals needed"
    ]
    if len(filtered) < 2:
        return None

    package_items = [item["visual_type"] for item in filtered[:3]]
    package_priority = "High" if signals["steps"] >= 6 or any(item["priority"] == "High" for item in filtered[:3]) else "Medium"
    package_confidence = min(95, int(sum(item["confidence"] for item in filtered[:3]) / min(3, len(filtered)) + 10))

    package_placement_hint = None
    if any(item in SCREENSHOT_TYPES.union(GIF_TYPES) for item in package_items):
        package_placement_hint = suggest_screenshot_placement(signals)
    elif any(item in DIAGRAM_TYPES for item in package_items):
        package_placement_hint = {
            "placement": "before_section",
            "display_text": "Before the procedure steps (context first)",
            "reason": "Start with context visuals, then proceed with configuration steps"
        }

    return {
        "visual_type": "Visual Package",
        "reason": "Multiple visual modalities improve comprehension for this section.",
        "score": round(sum(item["score"] for item in filtered[:3]), 1),
        "confidence": package_confidence,
        "confidence_category": get_confidence_category(package_confidence),
        "priority": package_priority,
        "content_type": filtered[0]["content_type"],
        "content_type_confidence": filtered[0]["content_type_confidence"],
        "complexity_score": filtered[0]["complexity_score"],
        "evidence": ["Package includes complementary visual types"],
        "rationale": [
            f"{signals['steps']} procedural steps detected",
            "Combines structural, UI, and sequence perspectives"
        ],
        "suggested_content": "Create visuals in this order: " + " -> ".join(package_items) + ".",
        "package_items": package_items,
        "gap_message": "Additional visual package recommended",
        "gap_coverage": "Coverage: 0/1 visual package (0%)",
        "existing_count": 0,
        "required_count": 1,
        "placement_hint": package_placement_hint,
        "diagram_blueprint": None,
        "generated_artifact": None
    }


def generate_suggested_content(visual_type, title, signals, matched_keywords):
    steps = signals["step_lines"][:8]

    if visual_type in {"Workflow Diagram", "Sequence Diagram", "GIF Tutorial"}:
        if steps:
            flow = " -> ".join(steps)
            return f"Create a {visual_type.lower()} for section '{title}' with this flow: {flow}."
        return f"Create a {visual_type.lower()} that shows start, action sequence, verification, and end states."

    if visual_type in {"Screenshot", "Configuration Screenshot"}:
        focus_terms = ", ".join(matched_keywords[:5]) if matched_keywords else "main UI controls"
        return f"Capture the UI state where users interact with: {focus_terms}. Highlight the active dialog or tab."

    if visual_type in {"Topology Diagram", "Architecture Diagram"}:
        return "Show systems and connections between PLC, edge device, gateway, and cloud endpoints. Label each channel."

    if visual_type == "Data Flow Diagram":
        return "Visualize source, transformation, and destination steps. Mark publish/subscribe or transfer paths with arrows."

    if visual_type == "Mapping Table":
        return "Build a table with columns: Source field, Target field, Data type, Constraint, Notes."

    if visual_type == "Before/After Comparison":
        return "Create a side-by-side visual comparing pre-change and post-change states, including key metrics."

    return "Provide a concise visual aid that explains the core concept and key decision points for this section."


def detect_visuals(title, content):
    content_lower = content.lower()
    signals = compute_signals(content)
    content_type, content_type_confidence = classify_content(title, content, signals)
    complexity_hint = complexity_recommendation(signals)
    existing_assets = detect_existing_visual_assets(content)
    relationship_count = len(extract_relationship_statements(content))
    diagram_blueprint = build_diagram_blueprint(content)
    results = []

    for rule in rules:
        visual_type = rule["visual_type"]
        score = 0.0
        evidence = []
        matched_keywords = []
        has_trigger = False
        relax_min_steps = False

        min_steps = rule.get("min_steps")
        if min_steps and signals["steps"] < min_steps:
            if visual_type == "Configuration Screenshot" and content_type in {"Concept", "Reference"}:
                ui_overview_hits = _count_pattern(content_lower, r"\b(ui|user interface|graphical user interface|editor|panel|settings|browse|tag browser|configuration)\b")
                if ui_overview_hits >= 3:
                    relax_min_steps = True
                    evidence.append("UI feature overview detected")
                else:
                    continue
            else:
                continue
        if min_steps:
            has_trigger = True

        min_words = rule.get("min_words")
        if min_words and signals["word_count"] < min_words:
            continue
        if min_words:
            has_trigger = True

        for keyword in rule.get("keywords", []):
            hits = _keyword_hits(content_lower, keyword)
            if hits > 0:
                score += hits * rule.get("weight", 1)
                matched_keywords.append(keyword)

        if rule.get("keywords") and not matched_keywords:
            continue

        if matched_keywords:
            has_trigger = True
            evidence.append("Keywords: " + ", ".join(matched_keywords[:6]))

        if min_steps and signals["steps"] >= min_steps:
            score += 2
            evidence.append(f"{signals['steps']} procedural steps detected")
        elif min_steps and relax_min_steps:
            ui_overview_hits = _count_pattern(content_lower, r"\b(ui|user interface|graphical user interface|editor|panel|settings|browse|tag browser|configuration)\b")
            score += 2 + min(3, ui_overview_hits // 2)

        if min_words and signals["word_count"] >= min_words:
            score += 1
            evidence.append(f"{signals['word_count']} words detected")

        if not has_trigger:
            continue

        allowed_types = rule.get("content_types", [])
        if allowed_types and content_type in allowed_types:
            score += 2
            evidence.append(f"Content classified as {content_type}")
        elif allowed_types:
            score = max(score - 2, 0)

        if complexity_hint == visual_type:
            score += 3
            evidence.append(f"Complexity rule suggests {visual_type}")

        if visual_type == "Screenshot" and signals["steps"] > 6:
            score = max(score - 2, 0)

        if visual_type == "GIF Tutorial" and signals["steps"] > 10:
            score += 2

        # Long procedures benefit from static workflow views, even without file-transfer keywords.
        if visual_type == "Workflow Diagram" and signals["steps"] >= 8:
            score += 7
            evidence.append("Long multi-step procedure detected")

        if visual_type in {"Architecture Diagram", "Topology Diagram"} and content_type == "Procedure":
            score = max(score - 2, 0)

        if visual_type == "Before/After Comparison" and content_type != "Troubleshooting":
            score = max(score - 1, 0)

        # Avoid architecture/data-flow false positives from keyword-only matches.
        if visual_type in RELATIONSHIP_REQUIRED_VISUALS and relationship_count == 0:
            continue

        if score <= 0:
            continue

        confidence = min(int(score * 11 + signals["ui_interactions"] * 2), 100)
        priority = build_priority(confidence, signals)
        rationale = [
            f"{signals['steps']} procedural steps detected",
            f"{signals['ui_interactions']} UI interactions detected",
            f"{signals['warnings']} warnings and {signals['verifications']} verification steps"
        ]

        gap = apply_gap_analysis(visual_type, existing_assets)
        if gap["gap_message"] == "No additional visuals needed":
            confidence = max(0, confidence - 22)
            if confidence < 40:
                priority = "Low"

        generated_artifact = build_generated_artifact(visual_type, title, content, signals, content_type)

        placement_hint = suggest_visual_placement(visual_type, content_type, signals)

        results.append({
            "visual_type": visual_type,
            "reason": rule["reason"],
            "score": round(score, 1),
            "confidence": confidence,
            "confidence_category": get_confidence_category(confidence),
            "priority": priority,
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "evidence": evidence,
            "rationale": rationale,
            "existing_visuals": existing_assets,
            "gap_message": gap["gap_message"],
            "gap_coverage": gap["coverage_display"],
            "existing_count": gap["existing_count"],
            "required_count": gap["required_count"],
            "placement_hint": placement_hint,
            "diagram_blueprint": diagram_blueprint if visual_type in DIAGRAM_TYPES else None,
            "generated_artifact": generated_artifact,
            "suggested_content": generate_suggested_content(
                visual_type,
                title,
                signals,
                matched_keywords
            )
        })

    results = sorted(results, key=lambda item: (item["confidence"], item["score"]), reverse=True)

    deduped = []
    seen = set()
    for item in results:
        if item["visual_type"] in seen:
            continue
        seen.add(item["visual_type"])
        deduped.append(item)

    # Drop any recommendation for a visual family that is already sufficiently covered.
    # existing_count >= 2 means at least 2 visuals of that type already exist in the section.
    deduped = [
        item for item in deduped
        if not (item.get("gap_message") == "No additional visuals needed" and item.get("existing_count", 0) >= 2)
    ]

    # Also drop lower-confidence covered items (existing_count == 1).
    deduped = [
        item for item in deduped
        if not (item.get("gap_message") == "No additional visuals needed" and item["confidence"] < 70)
    ]

    # If a section already has several visuals, suppress low-confidence additions to avoid over-recommendation.
    if existing_assets["total"] >= 2 and signals["steps"] <= 7 and content_type == "Procedure":
        deduped = [item for item in deduped if item["confidence"] >= 75]

    # Keep short, clear procedural guidance text-first unless complexity justifies a visual.
    if (
        content_type == "Procedure"
        and signals["steps"] <= 2
        and signals["action_verbs"] <= 5
        and signals["ui_interactions"] == 0
        and signals["word_count"] <= 55
        and signals["verifications"] == 0
    ):
        deduped = []

    deduped = select_final_recommendations(deduped, signals, content_type)

    package = build_visual_package(deduped, signals, content_type)
    if package:
        deduped.insert(0, package)

    if not deduped:
        deduped.append({
            "visual_type": "No recommendation",
            "reason": "No additional visuals needed based on current content and existing visuals",
            "score": 0,
            "confidence": 0,
            "confidence_category": "Low",
            "priority": "Low",
            "content_type": content_type,
            "content_type_confidence": content_type_confidence,
            "complexity_score": signals["complexity_score"],
            "evidence": [
                f"Existing visuals: {existing_assets['total']}"
            ],
            "rationale": [
                f"{signals['steps']} procedural steps detected",
                f"{signals['ui_interactions']} UI interactions detected",
                f"Complexity score {signals['complexity_score']}"
            ],
            "existing_visuals": existing_assets,
            "gap_message": "No additional visuals needed",
            "gap_coverage": f"Coverage: {existing_assets['total']}/1 visuals (100%)",
            "existing_count": existing_assets["total"],
            "required_count": 1,
            "placement_hint": None,
            "diagram_blueprint": diagram_blueprint,
            "generated_artifact": None,
            "suggested_content": "Keep text-only unless clarity issues appear during review."
        })

    return deduped[:3]