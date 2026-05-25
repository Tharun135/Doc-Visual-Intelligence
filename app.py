from flask import Flask, render_template, request
from analyzers.text_extractor import extract_text
from analyzers.section_splitter import split_sections
from analyzers.visual_detector import detect_visuals

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():

    results = []

    if request.method == "POST":

        file = request.files["document"]

        if file:

            filepath = file.filename
            file.save(filepath)

            text = extract_text(filepath)

            sections = split_sections(text)

            for section in sections:

                suggestions = detect_visuals(
                    section["title"],
                    section["content"]
                )

                results.append({
                    "title": section["title"],
                    "suggestions": suggestions
                })

    return render_template(
        "index.html",
        results=results
    )


if __name__ == "__main__":
    app.run(debug=True)