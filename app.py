from flask import Flask, render_template, request
from analyzers.text_extractor import extract_text
from analyzers.section_splitter import split_sections
from analyzers.visual_detector import detect_visuals, compute_signals

app = Flask(__name__)

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

            for section in sections:
                suggestions = detect_visuals(
                    section["title"],
                    section["content"]
                )

                step_lines = compute_signals(section["content"])["step_lines"]

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
        input_source=input_source
    )


if __name__ == "__main__":
    app.run(debug=True)