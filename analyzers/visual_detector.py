import json
import re


with open("rules/visual_rules.json", "r", encoding="utf-8") as file:
    rules = json.load(file)


ACTION_VERBS = {
    "open", "click", "select", "choose", "validate", "start", "verify",
    "check", "configure", "deploy", "save", "run", "import", "export",
    "upload", "download", "add", "remove", "connect", "set", "enter"
}


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

    if not deduped:
        deduped.append({
            "visual_type": "No recommendation",
            "reason": "No strong visual opportunity detected",
            "score": 0,
            "confidence": 0,
            "priority": "Low",
            "content_type": content_type,
            "complexity_score": signals["complexity_score"],
            "evidence": [],
            "rationale": [
                f"{signals['steps']} procedural steps detected",
                f"{signals['ui_interactions']} UI interactions detected",
                f"Complexity score {signals['complexity_score']}"
            ],
            "suggested_content": "Keep text-only unless clarity issues appear during review."
        })

    return deduped[:3]