# Visual Advisor

A Flask web application that analyzes technical documents and recommends where to add visual aids (flowcharts, screenshots, diagrams, GIFs, etc.) based on configurable rules.

## How It Works

1. Upload a text-based document through the web interface.
2. The document is split into sections by detecting headings and structural markers.
3. Each section is evaluated against a set of scoring rules to determine which visual type would best support the content.
4. Results are displayed per section with a confidence score and supporting evidence.

## Project Structure

```
visual-advisor/
├── app.py                          # Flask application entry point
├── rules/
│   └── visual_rules.json           # Configurable detection rules
├── analyzers/
│   ├── text_extractor.py           # Reads document content
│   ├── section_splitter.py         # Splits text into titled sections
│   └── visual_detector.py          # Scores sections and recommends visuals
├── templates/
│   └── index.html                  # Upload form and results page
└── static/                         # Static assets
```

## Supported Visual Types

| ID    | Visual Type          | Trigger                                      |
|-------|----------------------|----------------------------------------------|
| VR001 | Flowchart            | 3+ sequential procedure steps                |
| VR002 | Screenshot           | UI keywords (click, button, menu, dialog)    |
| VR003 | Architecture Diagram | System keywords (PLC, HMI, server, gateway)  |
| VR004 | Decision Tree        | Conditional language (if, else, otherwise)   |
| VR005 | Illustration         | Physical setup keywords (cable, mount, power)|
| VR006 | Workflow Diagram     | File transfer operations (import, export)    |
| VR007 | Code Example         | Structured data indicators (json, xml, yaml) |
| VR008 | Visual Summary       | Content blocks exceeding 100 words           |
| VR009 | GIF Tutorial         | Long interactive workflows (6+ steps)        |

## Getting Started

### Prerequisites

- Python 3.8+
- Flask

### Installation

```bash
pip install flask
```

### Running

```bash
python app.py
```

The application starts at `http://127.0.0.1:5000`.

## Adding Rules

Edit `rules/visual_rules.json` to add or modify detection rules. Each rule supports:

| Field         | Description                                    |
|---------------|------------------------------------------------|
| `id`          | Unique rule identifier                         |
| `keywords`    | List of trigger words to match in content      |
| `min_steps`   | Minimum procedure steps required to activate   |
| `min_words`   | Minimum word count required to activate        |
| `weight`      | Multiplier applied to keyword match score      |
| `visual_type` | The recommended visual type                    |
| `reason`      | Explanation shown in the results               |
