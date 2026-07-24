from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import csv
import os
import uuid
import re
import socket
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from werkzeug.exceptions import RequestEntityTooLarge
from analyzers.text_extractor import extract_text_from_upload
from analyzers.section_splitter import split_sections
from analyzers.visual_detector import detect_visuals, compute_signals, get_rule_catalog
from generators.plantuml_generator import render_plantuml

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Keep large POST payloads server-side to avoid overflowing cookie-based sessions.
POST_STATE_CACHE = {}

ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".pdf", ".docx"}
MAX_UPLOAD_MB = 25
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
PRIVACY_MODE = os.environ.get("DVI_PRIVACY_MODE", "1") == "1"
ENABLE_FEEDBACK_LOG = os.environ.get("DVI_ENABLE_FEEDBACK_LOG", "0") == "1" and not PRIVACY_MODE


def _is_allowed_file(filename):
    extension = Path(filename).suffix.lower()
    return extension in ALLOWED_EXTENSIONS


def _is_local_request() -> bool:
    remote_addr = request.remote_addr or ""
    return remote_addr in {"127.0.0.1", "::1", "localhost"}


def _privacy_self_test() -> dict:
    return {
        "privacy_mode": PRIVACY_MODE,
        "localhost_only": PRIVACY_MODE,
        "outbound_network_block_during_analysis": PRIVACY_MODE,
        "in_memory_upload_processing": True,
        "feedback_retention_enabled": ENABLE_FEEDBACK_LOG,
        "external_cdn_assets": False,
        "telemetry_enabled": False,
        "plantuml_cloud_fallback_enabled": os.environ.get("DVI_ALLOW_PLANTUML_API", "0") == "1",
        "database_enabled": False,
        "upload_storage_enabled": False,
    }


@contextmanager
def _block_outbound_network():
    """Block non-loopback socket connections while analysis runs."""
    if not PRIVACY_MODE:
        yield
        return

    original_socket = socket.socket

    class GuardedSocket(original_socket):
        def connect(self, address):
            host = address[0] if isinstance(address, tuple) and address else ""
            host_str = str(host).lower()
            if host_str not in {"127.0.0.1", "::1", "localhost"}:
                raise OSError("Outbound network blocked in privacy mode")
            return super().connect(address)

    socket.socket = GuardedSocket
    try:
        yield
    finally:
        socket.socket = original_socket


def _sanitize_svg(svg_text: str) -> str:
    """Best-effort SVG sanitizer for generated previews."""
    if not svg_text:
        return svg_text
    sanitized = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", svg_text, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r"\son[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r"\son[a-zA-Z]+\s*=\s*[^\s>]+", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"javascript:\s*", "", sanitized, flags=re.IGNORECASE)
    return sanitized


def _sanitize_mermaid_source(mermaid_text: str) -> str:
    """Remove Mermaid directives that can introduce interactive/script-like behavior."""
    if not mermaid_text:
        return mermaid_text
    lines = []
    for line in mermaid_text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("click "):
            continue
        if "javascript:" in stripped:
            continue
        lines.append(line)
    return "\n".join(lines)


def _sanitize_generated_artifacts(results: list[dict]) -> None:
    for section in results:
        for suggestion in section.get("suggestions", []):
            artifact = suggestion.get("generated_artifact")
            if isinstance(artifact, dict):
                if isinstance(artifact.get("svg"), str):
                    artifact["svg"] = _sanitize_svg(artifact["svg"])
                if isinstance(artifact.get("mermaid"), str):
                    artifact["mermaid"] = _sanitize_mermaid_source(artifact["mermaid"])
            if isinstance(suggestion.get("plantuml_code"), str):
                suggestion["plantuml_code"] = _sanitize_mermaid_source(suggestion["plantuml_code"])


@app.before_request
def enforce_localhost_only_when_private():
    if PRIVACY_MODE and not _is_local_request():
        return jsonify({"ok": False, "error": "Privacy mode is enabled: only localhost access is allowed."}), 403


def _load_feedback_summary():
    if PRIVACY_MODE:
        return {
            "has_data": False,
            "total": 0,
            "yes": 0,
            "no": 0,
            "acceptance_rate": 0,
            "by_visual_type": [],
        }

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
    if not ENABLE_FEEDBACK_LOG:
        return jsonify({"ok": False, "error": "Feedback logging is disabled in privacy mode."}), 403

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
        cached_text = request.form.get("cached_text", "")

        # If no new file or pasted text, fall back to the cached original text
        # so re-clicking "Analyze" re-runs the same document.
        if not pasted_text.strip() and not (file and file.filename):
            pasted_text = cached_text

        text = ""
        filename = ""
        if file and file.filename != "":
            filename = file.filename
            if not _is_allowed_file(filename):
                upload_error = "Unsupported file type. Use .txt, .md, .json, .pdf, or .docx."
            else:
                try:
                    text = extract_text_from_upload(file)
                    if not text.strip():
                        upload_error = "No readable text found in the uploaded file."
                except Exception:
                    upload_error = "Could not read the uploaded file. Please check file contents and format."

            input_source = "file"
            original_text = text
        elif pasted_text.strip():
            text = pasted_text
            input_source = "text"
            original_text = text

        if text:
            with _block_outbound_network():
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

            _sanitize_generated_artifacts(results)

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
        privacy=_privacy_self_test(),
        rule_catalog=get_rule_catalog(),
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
        privacy=_privacy_self_test(),
        rule_catalog=get_rule_catalog(),
        feedback_summary=_load_feedback_summary(),
        upload_error=f"File is too large. Maximum allowed size is {MAX_UPLOAD_MB}MB.",
    ), 413


@app.route("/privacy/self-test", methods=["GET"])
def privacy_self_test():
    return jsonify({"ok": True, "checks": _privacy_self_test()})


@app.route("/privacy/report", methods=["GET"])
def privacy_report():
    checks = _privacy_self_test()
    route_rules = {rule.rule for rule in app.url_map.iter_rules()}
    feedback_disabled = not ENABLE_FEEDBACK_LOG
    plantuml_disabled = PRIVACY_MODE
    endpoint_surface_minimized = "/feedback" not in route_rules or feedback_disabled
    ordered = [
        ("Offline Mode Enabled", checks["privacy_mode"]),
        ("No Internet Endpoints Configured", checks["localhost_only"] and not checks["plantuml_cloud_fallback_enabled"]),
        ("No CDN Assets", checks["external_cdn_assets"] is False),
        ("No Telemetry", checks["telemetry_enabled"] is False),
        ("No Upload Storage", checks["upload_storage_enabled"] is False),
        ("No Feedback Logging", checks["feedback_retention_enabled"] is False),
        ("No Database", checks["database_enabled"] is False),
        ("PlantUML Cloud Disabled", checks["plantuml_cloud_fallback_enabled"] is False),
        ("Mermaid Local", checks["external_cdn_assets"] is False),
        ("Upload Processing In Memory", checks["in_memory_upload_processing"]),
        ("Outbound Network Block During Analysis", checks["outbound_network_block_during_analysis"]),
        ("Endpoint Surface Minimized", endpoint_surface_minimized and plantuml_disabled),
    ]
    passed = sum(1 for _, ok in ordered if ok)
    score = int(round((passed / len(ordered)) * 100)) if ordered else 0
    return jsonify({
        "ok": True,
        "score": score,
        "checks": [{"name": name, "pass": ok} for name, ok in ordered],
    })


@app.after_request
def add_security_headers(response):
    csp = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ])
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), accelerometer=(), magnetometer=()"
    return response


@app.route("/generate/plantuml", methods=["POST"])
def generate_plantuml_route():
    """Render PlantUML source code to SVG via the MCP server."""
    if PRIVACY_MODE:
        return jsonify({"ok": False, "error": "PlantUML render endpoint is disabled in privacy mode."}), 403

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