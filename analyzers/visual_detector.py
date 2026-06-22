import json
import re


with open("rules/visual_rules.json", "r", encoding="utf-8") as file:
    rules = json.load(file)

with open("rules/knowledge_model.json", "r", encoding="utf-8") as file:
    knowledge_model = json.load(file)


ACTION_VERBS = {
    "open", "click", "select", "choose", "validate", "start", "verify",
    "check", "configure", "deploy", "save", "run", "import", "export",
    "upload", "download", "add", "remove", "connect", "set", "enter"
}

CHECKPOINT_TERMS = {
    "validate", "verify", "confirm", "review", "save", "apply", "test", "status"
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


def compute_signals(content):
    step_lines = extract_procedure_steps(content)
    numbered_steps = _count_pattern(content, r"^\s*(?:\d+[\.)]|step\s+\d+)")
    nested_steps = _count_pattern(content, r"^\s{2,}(?:[-*]|[a-z][\.)])")
    warnings = _count_pattern(content, r"\b(warning|caution|important|notice)\b")
    notes = _count_pattern(content, r"\b(note|tip|hint)\b")
    prerequisites = _count_pattern(content, r"\b(prerequisite|requirement|before you begin|precondition)\b")
    verifications = _count_pattern(content, r"\b(verify|validation|validate|check status|confirm)\b")
    ui_interactions = _count_pattern(content, r"\b(click|select|menu|dialog|tab|button|panel)\b")
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
        "word_count": word_count,
        "complexity_score": round(complexity_score, 1)
    }


def classify_content(title, content, signals):
    title_lower = title.lower()
    content_lower = content.lower()

    if re.search(r"\b(troubleshoot|error|failure|issue|fault)\b", title_lower + " " + content_lower):
        return "Troubleshooting"

    if signals["steps"] >= 3 or re.search(r"\b(procedure|steps|how to)\b", title_lower):
        return "Procedure"

    if re.search(r"\b(topology|architecture|system layout|network|integration)\b", title_lower + " " + content_lower):
        return "Architecture"

    if re.search(r"\b(parameter|field|property|reference|api|table)\b", title_lower + " " + content_lower):
        return "Reference"

    return "Concept"


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

    # Place visuals where users need a confidence checkpoint (validation/verification/save).
    for index, step in enumerate(steps):
        step_lower = step.lower()
        if any(term in step_lower for term in CHECKPOINT_TERMS):
            return {
                "step_number": index + 1,
                "step_text": step,
                "reason": "Checkpoint step detected where users need confirmation"
            }

    middle = max(1, len(steps) // 2)
    return {
        "step_number": middle,
        "step_text": steps[middle - 1],
        "reason": "Mid-workflow placement provides orientation in long procedures"
    }


def _normalize_node_id(label):
    return re.sub(r"[^a-zA-Z0-9]", "", label) or "Node"


def extract_entities(content):
    content_lower = content.lower()
    entities = []
    entities_cfg = knowledge_model.get("entities", {})
    for name, metadata in entities_cfg.items():
        aliases = metadata.get("aliases", [])
        for alias in aliases:
            pattern = r"\b" + re.escape(alias.lower()) + r"\b"
            if re.search(pattern, content_lower):
                entities.append(name)
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
    nodes = extract_entities(content)

    if len(nodes) < 2:
        return None

    relationships = extract_relationships(nodes)

    mermaid_lines = ["graph LR"]
    for src, dst in relationships:
        mermaid_lines.append(f"{_normalize_node_id(src)}[{src}] --> {_normalize_node_id(dst)}[{dst}]")

    return {
        "nodes": nodes,
        "relationships": [f"{src} -> {dst}" for src, dst in relationships],
        "mermaid": "\n".join(mermaid_lines)
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
            "gap_message": "Evaluate manually"
        }

    existing_count = existing_assets.get(family, 0)
    required_count = 1

    if existing_count >= required_count:
        gap_message = "No additional visuals needed"
    else:
        gap_message = "Additional visual recommended"

    return {
        "family": family,
        "existing_count": existing_count,
        "required_count": required_count,
        "gap_message": gap_message
    }


def build_visual_package(recommendations, signals, placement_hint):
    filtered = [item for item in recommendations if item["visual_type"] != "No recommendation" and item["confidence"] >= 45]
    if len(filtered) < 2:
        return None

    package_items = [item["visual_type"] for item in filtered[:3]]
    package_priority = "High" if signals["steps"] >= 6 or any(item["priority"] == "High" for item in filtered[:3]) else "Medium"
    package_confidence = min(95, int(sum(item["confidence"] for item in filtered[:3]) / min(3, len(filtered)) + 10))

    return {
        "visual_type": "Visual Package",
        "reason": "Multiple visual modalities improve comprehension for this section.",
        "score": round(sum(item["score"] for item in filtered[:3]), 1),
        "confidence": package_confidence,
        "priority": package_priority,
        "content_type": filtered[0]["content_type"],
        "complexity_score": filtered[0]["complexity_score"],
        "evidence": ["Package includes complementary visual types"],
        "rationale": [
            f"{signals['steps']} procedural steps detected",
            "Combines structural, UI, and sequence perspectives"
        ],
        "suggested_content": "Create visuals in this order: " + " -> ".join(package_items) + ".",
        "package_items": package_items,
        "gap_message": "Additional visual package recommended",
        "placement_hint": placement_hint if any(item in SCREENSHOT_TYPES.union(GIF_TYPES) for item in package_items) else None,
        "diagram_blueprint": None
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
    content_type = classify_content(title, content, signals)
    complexity_hint = complexity_recommendation(signals)
    existing_assets = detect_existing_visual_assets(content)
    placement_hint = suggest_screenshot_placement(signals)
    diagram_blueprint = build_diagram_blueprint(content)
    results = []

    for rule in rules:
        visual_type = rule["visual_type"]
        score = 0.0
        evidence = []
        matched_keywords = []

        for keyword in rule.get("keywords", []):
            hits = _keyword_hits(content_lower, keyword)
            if hits > 0:
                score += hits * rule.get("weight", 1)
                matched_keywords.append(keyword)

        if matched_keywords:
            evidence.append("Keywords: " + ", ".join(matched_keywords[:6]))

        min_steps = rule.get("min_steps")
        if min_steps and signals["steps"] >= min_steps:
            score += 2
            evidence.append(f"{signals['steps']} procedural steps detected")

        min_words = rule.get("min_words")
        if min_words and signals["word_count"] >= min_words:
            score += 1
            evidence.append(f"{signals['word_count']} words detected")

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

        if visual_type in {"Architecture Diagram", "Topology Diagram"} and content_type == "Procedure":
            score = max(score - 2, 0)

        if visual_type == "Before/After Comparison" and content_type != "Troubleshooting":
            score = max(score - 1, 0)

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

        results.append({
            "visual_type": visual_type,
            "reason": rule["reason"],
            "score": round(score, 1),
            "confidence": confidence,
            "priority": priority,
            "content_type": content_type,
            "complexity_score": signals["complexity_score"],
            "evidence": evidence,
            "rationale": rationale,
            "existing_visuals": existing_assets,
            "gap_message": gap["gap_message"],
            "existing_count": gap["existing_count"],
            "required_count": gap["required_count"],
            "placement_hint": placement_hint if visual_type in SCREENSHOT_TYPES.union(GIF_TYPES) else None,
            "diagram_blueprint": diagram_blueprint if visual_type in DIAGRAM_TYPES else None,
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

    deduped = [
        item for item in deduped
        if not (item.get("gap_message") == "No additional visuals needed" and item["confidence"] < 70)
    ]

    # If a section already has several visuals, suppress low-confidence additions to avoid over-recommendation.
    if existing_assets["total"] >= 2 and signals["steps"] <= 7 and content_type == "Procedure":
        deduped = [item for item in deduped if item["confidence"] >= 75]

    package = build_visual_package(deduped, signals, placement_hint)
    if package:
        deduped.insert(0, package)

    if not deduped:
        deduped.append({
            "visual_type": "No recommendation",
            "reason": "No additional visuals needed based on current content and existing visuals",
            "score": 0,
            "confidence": 0,
            "priority": "Low",
            "content_type": content_type,
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
            "existing_count": existing_assets["total"],
            "required_count": 1,
            "placement_hint": None,
            "diagram_blueprint": diagram_blueprint,
            "suggested_content": "Keep text-only unless clarity issues appear during review."
        })

    return deduped[:3]