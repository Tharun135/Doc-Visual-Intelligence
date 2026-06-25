from flask import Flask, render_template, request, jsonify
import csv
from datetime import datetime
from pathlib import Path
from analyzers.text_extractor import extract_text
from analyzers.section_splitter import split_sections
from analyzers.visual_detector import detect_visuals, compute_signals

app = Flask(__name__)


def _load_feedback_summary():
    csv_path = Path(app.root_path) / "feedback" / "recommendation_feedback.csv"
    if not csv_path.exists():
        return {
            "has_data": False,
            "total": 0,
            "yes": 0,
            "no": 0,
            "acceptance_rate": 0,
            "by_visual_type": [],
        }

    totals = {}
    yes_total = 0
    no_total = 0

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            visual_type = (row.get("visual_type") or "Unknown").strip() or "Unknown"
            useful = (row.get("useful") or "").strip().lower()
            if useful not in {"yes", "no"}:
                continue

            if visual_type not in totals:
                totals[visual_type] = {"yes": 0, "no": 0, "total": 0}
            totals[visual_type][useful] += 1
            totals[visual_type]["total"] += 1

            if useful == "yes":
                yes_total += 1
            else:
                no_total += 1

    total = yes_total + no_total
    acceptance_rate = int((yes_total / total) * 100) if total else 0
    by_visual_type = []
    for visual_type, stats in totals.items():
        vt_total = stats["total"]
        vt_rate = int((stats["yes"] / vt_total) * 100) if vt_total else 0
        by_visual_type.append({
            "visual_type": visual_type,
            "yes": stats["yes"],
            "no": stats["no"],
            "total": vt_total,
            "acceptance_rate": vt_rate,
        })

    by_visual_type.sort(key=lambda item: item["total"], reverse=True)

    return {
        "has_data": total > 0,
        "total": total,
        "yes": yes_total,
        "no": no_total,
        "acceptance_rate": acceptance_rate,
        "by_visual_type": by_visual_type,
    }


@app.route("/feedback", methods=["POST"])
def feedback():
    payload = request.get_json(silent=True) or {}
    section_title = str(payload.get("section_title", "")).strip()
    visual_type = str(payload.get("visual_type", "")).strip()
    useful = str(payload.get("useful", "")).strip().lower()
    confidence = payload.get("confidence")

    if not section_title or not visual_type or useful not in {"yes", "no"}:
        return jsonify({"ok": False, "error": "Invalid feedback payload"}), 400

    feedback_dir = Path(app.root_path) / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    csv_path = feedback_dir / "recommendation_feedback.csv"
    write_header = not csv_path.exists()

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "section_title", "visual_type", "useful", "confidence"])
        writer.writerow([
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            section_title,
            visual_type,
            useful,
            confidence if confidence is not None else "",
        ])

    return jsonify({"ok": True})

@app.route("/", methods=["GET", "POST"])
def home():

    results = []
    original_text = ""
    input_source = "" # 'file' or 'text' or ''

    if request.method == "POST":
        file = request.files.get("document")
        pasted_text = request.form.get("pasted_text", "")

        text = ""
        filename = ""
        if file and file.filename != "":
            filename = file.filename
            # Read file stream directly to avoid temp file pollution, fallback to saving if needed
            try:
                text = file.read().decode("utf-8")
            except Exception:
                # Fallback to local save if decode fail or stream issue
                import os
                temp_path = os.path.join(app.root_path, "temp_upload.txt")
                file.save(temp_path)
                text = extract_text(temp_path)
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            input_source = "file"
            original_text = text
        elif pasted_text.strip():
            text = pasted_text
            input_source = "text"
            original_text = text

        if text:
            sections = split_sections(text)

            precomputed_signals = [compute_signals(section["content"]) for section in sections]

            for index, section in enumerate(sections):
                next_steps = precomputed_signals[index + 1]["steps"] if index + 1 < len(sections) else 0
                section_context = {
                    "previous_title": sections[index - 1]["title"] if index > 0 else "",
                    "next_title": sections[index + 1]["title"] if index + 1 < len(sections) else "",
                    "next_steps": next_steps,
                }

                suggestions = detect_visuals(
                    section["title"],
                    section["content"],
                    section_context,
                )

                step_lines = precomputed_signals[index]["step_lines"]

                results.append({
                    "title": section["title"],
                    "content": section["content"],
                    "step_lines": step_lines,
                    "suggestions": suggestions
                })

    return render_template(
        "index.html",
        results=results,
        original_text=original_text,
        input_source=input_source,
        feedback_summary=_load_feedback_summary(),
    )


if __name__ == "__main__":
    app.run(debug=True)