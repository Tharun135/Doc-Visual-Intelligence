from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import csv
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from werkzeug.exceptions import RequestEntityTooLarge
from analyzers.text_extractor import extract_text
from analyzers.section_splitter import split_sections
from analyzers.visual_detector import detect_visuals, compute_signals
from generators.plantuml_generator import render_plantuml

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Keep large POST payloads server-side to avoid overflowing cookie-based sessions.
POST_STATE_CACHE = {}

ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".pdf", ".docx"}
MAX_UPLOAD_MB = 25
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _is_allowed_file(filename):
    extension = Path(filename).suffix.lower()
    return extension in ALLOWED_EXTENSIONS


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

    # Read any payload produced by a previous POST (PRG pattern).
    post_state_id = session.pop("home_post_state_id", None)
    post_state = POST_STATE_CACHE.pop(post_state_id, None) if post_state_id else None
    results = post_state.get("results", []) if post_state else []
    original_text = post_state.get("original_text", "") if post_state else ""
    input_source = post_state.get("input_source", "") if post_state else ""  # 'file' or 'text' or ''
    upload_error = post_state.get("upload_error", "") if post_state else ""

    if request.method == "POST":
        file = request.files.get("document")
        pasted_text = request.form.get("pasted_text", "")

        text = ""
        filename = ""
        if file and file.filename != "":
            filename = file.filename
            if not _is_allowed_file(filename):
                upload_error = "Unsupported file type. Use .txt, .md, .json, .pdf, or .docx."
            else:
                temp_path = ""
                extension = Path(filename).suffix.lower()
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                        file.save(temp_file.name)
                        temp_path = temp_file.name

                    text = extract_text(temp_path)
                    if not text.strip():
                        upload_error = "No readable text found in the uploaded file."
                except Exception:
                    upload_error = "Could not read the uploaded file. Please check file contents and format."
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)

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

            # ── Reuse detection ─────────────────────────────────────
            # Build a fingerprint for each screenshot recommendation from
            # its focus area + include list, then flag later sections that
            # share the same fingerprint with the first-seen section title.
            _screenshot_types = {"Screenshot", "Configuration Screenshot", "Annotated Screenshot"}
            _seen_fingerprints: dict[str, str] = {}   # fingerprint → section title

            for result in results:
                for suggestion in result["suggestions"]:
                    if suggestion.get("visual_type") not in _screenshot_types:
                        continue
                    spec = (
                        suggestion.get("generated_artifact") or {}
                    ).get("specification") or {}
                    focus = spec.get("focus_area", "").strip().lower()
                    include = " | ".join(
                        sorted(i.lower() for i in spec.get("capture", {}).get("include", []))
                    )
                    fingerprint = f"{focus}::{include}"
                    if len(fingerprint) < 4:
                        continue
                    if fingerprint in _seen_fingerprints:
                        suggestion["reuse_warning"] = (
                            f'This screenshot may already exist in section: "{_seen_fingerprints[fingerprint]}"'
                        )
                    else:
                        _seen_fingerprints[fingerprint] = result["title"]
                        suggestion["reuse_warning"] = None
            # ── End reuse detection ──────────────────────────────────

        post_state_id = uuid.uuid4().hex
        POST_STATE_CACHE[post_state_id] = {
            "results": results,
            "original_text": original_text,
            "input_source": input_source,
            "upload_error": upload_error,
        }
        session["home_post_state_id"] = post_state_id
        return redirect(url_for("home"))

    return render_template(
        "index.html",
        results=results,
        original_text=original_text,
        input_source=input_source,
        feedback_summary=_load_feedback_summary(),
        upload_error=upload_error,
    )


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return render_template(
        "index.html",
        results=[],
        original_text="",
        input_source="file",
        feedback_summary=_load_feedback_summary(),
        upload_error=f"File is too large. Maximum allowed size is {MAX_UPLOAD_MB}MB.",
    ), 413


@app.route("/generate/plantuml", methods=["POST"])
def generate_plantuml_route():
    """Render PlantUML source code to SVG via the MCP server."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()

    if not code:
        return jsonify({"ok": False, "error": "No PlantUML code provided"}), 400

    svg, error = render_plantuml(code)

    if error or not svg:
        return jsonify({"ok": False, "error": error or "Render produced no output"}), 500

    return jsonify({"ok": True, "svg": svg})


if __name__ == "__main__":
    app.run(debug=True)