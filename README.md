# Doc Visual Advisor

A Flask-based technical document analyzer that identifies where visual aids strengthen readability and understanding. The tool detects procedural steps, system architectures, conditional logic, and configuration workflows—then recommends placement locations with transparent confidence scoring and legible rule traces showing exactly which signals triggered each recommendation.

**Core Principle:** Trust the *placement* hint (where a visual belongs), but verify the *generated content* quality (whether auto-generated visual content is draft-ready). These are scored independently so writers can make informed authoring decisions.

## Privacy-First Local Processing

This application now defaults to a local-only privacy posture designed for confidential technical documentation.

- Localhost-only access is enforced in Privacy Mode.
- Uploaded files are processed in memory (no persistent `uploads/` storage).
- Feedback retention is disabled by default in Privacy Mode.
- Telemetry is disabled.
- Remote CDN assets are disabled (local Mermaid fallback shim + local/system fonts).
- PlantUML public API fallback is disabled by default.

### Privacy Mode Defaults

Environment variables:

- `DVI_PRIVACY_MODE=1` (default): Enables privacy mode and localhost-only access.
- `DVI_ENABLE_FEEDBACK_LOG=0` (default): Disables feedback CSV retention.
- `DVI_ALLOW_PLANTUML_API=0` (default): Disables remote PlantUML rendering fallback.

### Privacy Self-Test

Use the built-in self-test endpoint:

- `GET /privacy/self-test`

Expected checks in privacy mode:

- `privacy_mode: true`
- `localhost_only: true`
- `in_memory_upload_processing: true`
- `feedback_retention_enabled: false`
- `external_cdn_assets: false`
- `telemetry_enabled: false`

This endpoint exists to support enterprise security review with machine-verifiable runtime flags.

## Enterprise Security Hardening

### Runtime Guardrails

- **Parser limits**:
   - Maximum upload size: 25 MB (`MAX_CONTENT_LENGTH`)
   - Maximum PDF pages: 500
   - Maximum parser runtime: 30 seconds for PDF/DOCX extraction
   - Maximum DOCX uncompressed size: 100 MB (zip-bomb mitigation)
- **Outbound network guard during analysis**:
   - In privacy mode, non-loopback socket connections are blocked while document analysis executes.
- **Endpoint minimization in privacy mode**:
   - Feedback retention endpoint is effectively disabled.
   - PlantUML render endpoint is disabled.

### Browser Hardening

The app sets strict security headers on every response:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy`

Default CSP:

```text
default-src 'self';
script-src 'self';
img-src 'self' data:;
style-src 'self' 'unsafe-inline';
object-src 'none';
base-uri 'none';
frame-ancestors 'none';
form-action 'self';
connect-src 'self'
```

### SVG and Mermaid Injection Controls

- Generated SVG previews are sanitized server-side to strip:
   - `<script>` blocks
   - inline event handlers like `onload=`
   - `javascript:` URLs
- Mermaid source is sanitized to remove interactive directives like `click` and `javascript:` links.
- Mermaid runtime is initialized with `securityLevel: 'strict'` and `htmlLabels: false`.

## Offline Verification Report

Use the in-app **Verify Privacy** button or call:

- `GET /privacy/report`

The report returns a machine-readable checklist and score (0–100), including:

- Offline mode enabled
- No internet endpoints configured
- No CDN assets
- No telemetry
- No upload storage
- No feedback logging
- No database
- PlantUML cloud disabled
- Mermaid local
- Upload processing in memory
- Outbound network blocked during analysis
- Endpoint surface minimized

## Threat Model Summary

| Threat | Mitigation |
|---|---|
| Document leaves machine | Localhost-only mode + no cloud upload endpoints in privacy mode |
| Upload persistence | In-memory processing; no upload directory |
| Malicious PDF/DOCX payload | Size/page/time limits + DOCX zip expansion checks |
| Browser XSS via generated artifacts | SVG sanitization + CSP + Mermaid strict mode |
| Silent external calls | Local assets only + PlantUML cloud fallback disabled by default |
| Data retention concerns | Feedback logging disabled by default in privacy mode |
| Excess attack surface | Privacy report + endpoint minimization checks |

## Dependency Security Checks

Run regularly:

```bash
python -m pip install pip-audit safety
pip-audit
safety check
```

These checks should be included in CI for release gating.

## How It Works

1. **Document Upload** — Paste or load a text-based document (Markdown, plain text, or JSON) through the web interface.

2. **Section Detection** — The document is split into titled sections using heading detection and structural markers (e.g., "## Prerequisites", "### Configuration Steps").

3. **Content Classification** — Each section is classified by type (Procedure, Concept, Architecture, Reference, Troubleshooting) to narrow the recommendation set.

4. **Rule-Based Visual Matching** — The section is evaluated against 15 detection rules (keyword triggers, step counts, complexity signals) to identify which visual types would best support the content.

5. **Confidence Scoring** (Two-Tier System)
   - **Placement Confidence** (35–98%): Estimates how reliably the tool identified *where* a visual belongs in the document. Anchored-to-step placements score 95–98%; before-section placements score 90–95%; generic placements score 35–45%.
   - **Generation Confidence** (0–100%): Estimates whether auto-generated visual *content* is trustworthy enough to use as a draft. Screenshot, Architecture, and Workflow diagrams typically score 50–85% depending on signal strength. Decision Trees always score 0% because auto-generation is disabled.

6. **Rule Evidence** — Each recommendation displays a "Why this recommendation fired" section that explains:
   - Which rule fired and why (for example, "Multi-Step Workflow Rule" with `PR_WORKFLOW` shown as a secondary ID)
   - Placement confidence reasoning (e.g., "Anchored to specific procedure step (98%)")
   - Generation confidence reasoning (e.g., "3 control flow branches; multi-step schema clarity is good (72%)")
   - Worthiness score (how strong the evidence is: 1–10)
   - Primary signal evidence (e.g., "4 procedural steps, 2 conditional branches, 1 verification step")

7. **Results Display** — Recommendations are shown per section with:
   - A placement hint (text describing where to insert the visual)
   - Side-by-side confidence tiers (placement % in teal, generation % in amber)
   - An example or mockup of what the visual *could* look like
   - Full rule trace explaining the reasoning
   - A warning if generation confidence is below 60%: *"Auto-generated content is weak for this case. Use the placement hint and draft the visual manually."*

## Features

### Version 2: Content Classification
- Detects section type (Procedure, Concept, Architecture, Reference, Troubleshooting).
- Scores procedure complexity based on step count, nesting depth, warnings, notes, prerequisites, and verification language.
- Assigns visual priority (High, Medium, Low) to help writers focus effort on high-impact sections.

### Version 3: Visual Gap Analysis
- Detects existing screenshots or diagrams to suppress unnecessary recommendations.
- Recommends screenshot insertion points (e.g., after validation steps).
- Packages multiple visual type recommendations when a section benefits from more than one.
- Extracts component nodes and relationships for architecture sections and outputs graph blueprints.

### Version 4: Entity Normalization
- Uses a knowledge model (`rules/knowledge_model.json`) with canonicalized entities and comprehensive aliases.
- Maps synonyms ("CPU", "S7-1500", "microcontroller") to canonical names ("Controller") to prevent graph fragmentation.
- Supports generic entity types (device, application, runtime, network_component, interface, system, external_system).
- Provides content-type classification confidence scores (e.g., "Procedure (95%)") to help identify ambiguous sections.

### Version 5: Native Visual Generation
- Generates downloadable SVG flowcharts directly from procedural text steps.
- Renders SVG architecture diagrams from detected semantic components and relationships.
- Applies unified professional theme (Siemens Teal) across generated visuals.
- Uses CSS keyframe animations within SVGs to show data flow direction.
- Ensures robust inline SVG rendering with UUID-based marker references for multi-diagram pages.

### Version 6: Transparent Confidence & Disabled Decision Trees
- Splits confidence into placement (where) and generation (content quality) tiers, scored independently.
- Shows legible rule traces instead of opaque percentages—explains exactly which signals fired.
- **Disables auto-generated Decision Trees** because conditional extraction remains heuristic and produces weak output.
- Decision Tree recommendations still appear when conditional logic is detected, but show an example template labeled "Example Structure" with greyed-out styling and explanatory text: *"Auto-generation is disabled for decision trees. Use the placement hint above to manually author a visual that reflects your document's actual conditions and outcomes."*
- Ensures loading-state skeleton is visually unmistakable as a template (opacity 0.55, grayscale filter, "Template" status badge, descriptive disclaimer text).

## Current Safety Constraints

### Decision Tree Auto-Generation Disabled
Decision-tree extraction from conditional language remains heuristic and often produces weak output (garbled node labels, truncated action text, unreliable branching). Rather than show broken output with false confidence, the tool:
- **Still detects** decision-heavy sections (conditional keywords like "if", "else", "otherwise", "depends on").
- **Still recommends** placement (anchored to the section where logic is explained).
- **Does NOT auto-generate** the tree visual. Instead, shows a greyed-out "Example Structure" template.
- **Displays 0% generation confidence** with clear explanation: *"Auto-generation is disabled for decision trees."*

A writer can see the placement is sound (95%+ confidence) but choose to hand-author the decision tree using the placement hint, rather than trusting a weak auto-generated visual.

### Loading-State Template Visibility
Decision Tree recommendations show a visual template (generic "Condition?", "Yes/No", "Action A/B" nodes with dashed connectors) while content is being processed. This template is visually marked as a placeholder:
- **Greyed out** (opacity 0.55 on the box, grayscale(80%) + opacity(0.7) on the diagram).
- **Status badge**: Labeled "Template" instead of a progress indicator.
- **Title**: "Decision Logic Tree — Example Structure" instead of just the visual type.
- **Explanatory text**: Clearly states it's not real output and that manual authoring is required.

This prevents confusion between the generic skeleton and actual (weak) generated output.

### Why These Constraints?
The tool is built on rule-based heuristics, not machine learning. It excels at:
- ✓ Identifying *where* visuals belong (placement confidence: 90–98%)
- ✓ Detecting *what type* of visual is needed (flowchart vs. architecture vs. screenshot)
- ✓ Generating *some* visual types well when signals are strong (screenshots, architecture diagrams: 70–85% draft-ready)

It struggles with:
- ✗ Extracting *conditional logic* reliably from natural language (decision trees: too many false branches)
- ✗ Producing *polished* auto-generated content without domain-specific tuning

**Solution**: Separate placement from generation confidence so writers can trust placement hints without over-trusting content quality. Disable auto-generation for weak signal types (Decision Trees) and let writers manually author from the placement recommendation.

## Project Structure

```text
Doc-Visual-Intelligence/
├── app.py                                   # Flask application entry point
├── requirements.txt                         # Python package dependencies
├── requirements-desktop.txt                 # Desktop dependencies (PySide6 + PyInstaller)
├── README.md                                # This file
│
├── desktop/
│   ├── main.py                              # PySide6 desktop application entry point
│   ├── DocVisualAdvisor.spec                # PyInstaller build spec
│   ├── build_windows.ps1                    # Windows packaging script
│   └── build_unix.sh                        # macOS/Linux packaging script
│
├── rules/
│   ├── visual_rules.json                    # Rule definitions (keywords, triggers, visual types)
│   ├── knowledge_model.json                 # Entity canonicalization and aliases
│   └── rule_definitions.py                  # Python rules engine
│
├── analyzers/
│   ├── text_extractor.py                    # Extracts document content (text, markdown, JSON)
│   ├── section_splitter.py                  # Splits documents into titled sections
│   └── visual_detector.py                   # Main detection engine: analyzes sections and scores visual recommendations
│
├── generators/
│   ├── architecture_parser.py               # Parses architecture descriptions into node/relationship graphs
│   ├── architecture_renderer.py             # Renders SVG architecture diagrams
│   ├── svg_flow_renderer.py                 # Renders SVG flowcharts from procedural steps
│   ├── plantuml_generator.py                # PlantUML diagram generation
│   ├── screenshot_specification.py          # Screenshot mockup generation
│   └── ...other visual generators           # Specialized renderers for each visual type
│
├── orchestrator/
│   └── visual_orchestrator.py               # Orchestrates detection and generation pipeline
│
├── templates/
│   └── index.html                           # Web UI: upload form, results display, rule traces, confidence tiers
│
├── static/
│   ├── app.js                               # Client-side interactivity (expand/collapse, filtering)
│   ├── style.css                            # UI styling (Siemens Teal theme)
│   └── ...other assets
│
├── feedback/
│   └── recommendation_feedback.csv          # Optional: user feedback on recommendations (for future ML training)
│
└── .venv/                                   # Python virtual environment (created during installation)
```

### Key Files Explained

- **`app.py`** — Flask application that serves the web interface and processes document uploads.
- **`analyzers/visual_detector.py`** — Core recommendation engine. Detects visual types, computes placement confidence, generation confidence, and rule traces.
- **`rules/visual_rules.json`** — JSON rule definitions. Each rule has keywords, minimum step counts, and visual type mappings.
- **`templates/index.html`** — Web UI renders recommendations with confidence tiers, rule traces, and generated previews.
- **`generators/`** — Specialized modules for rendering each visual type (SVG architecture, SVG flowcharts, screenshots, etc.).

### Customization Points

1. **Add detection rules** → Edit `rules/visual_rules.json`
2. **Add entity aliases** → Edit `rules/knowledge_model.json`
3. **Modify UI appearance** → Edit `templates/index.html` and `static/style.css`
4. **Add custom visual generators** → Extend `generators/` directory with new renderer modules

## Supported Visual Types

| ID    | Visual Type          | Trigger                                      | Status |
|-------|----------------------|----------------------------------------------|--------|
| VR001 | Flowchart            | 3+ sequential procedure steps                | ✓ Auto-generated SVG |
| VR002 | Screenshot           | UI keywords (click, button, menu, dialog)    | ✓ Auto-generated mockup |
| VR003 | Architecture Diagram | System keywords (PLC, HMI, server, gateway)  | ✓ Auto-generated SVG |
| VR004 | Decision Tree        | Conditional language (if, else, otherwise)   | ⚠️ Manual authoring required |
| VR005 | Illustration         | Physical setup keywords (cable, mount, power)| ⚠️ Template mockup |
| VR006 | Workflow Diagram     | File transfer operations (import, export)    | ✓ Auto-generated SVG |
| VR007 | Code Example         | Structured data indicators (json, xml, yaml) | ✓ Auto-generated |
| VR008 | Visual Summary       | Content blocks exceeding 100 words           | ⚠️ Template mockup |
| VR009 | GIF Tutorial         | Long interactive workflows (6+ steps)        | ⚠️ Template mockup |
| VR010 | Topology Diagram     | System communication terms (device, PLC, cloud, gateway) | ✓ Auto-generated SVG |
| VR011 | Configuration Screenshot | Multi-step configuration UI interactions | ✓ Auto-generated mockup |
| VR012 | Data Flow Diagram    | Data movement terms (collect, send, publish, subscribe) | ✓ Auto-generated SVG |
| VR013 | Mapping Table        | Field mapping terms (source, target, datatype) | ✓ Auto-generated |
| VR014 | Before/After Comparison | State comparison language (before, after, changed) | ⚠️ Template mockup |
| VR015 | Sequence Diagram     | Ordered sequence language with multiple steps | ✓ Auto-generated |

**Legend:**
- **✓ Auto-generated SVG**: Generates downloadable SVG visual automatically.
- **✓ Auto-generated mockup**: Generates a visual mockup automatically.
- **✓ Auto-generated**: Generates structured output (code snippet, table, etc.) automatically.
- **⚠️ Manual authoring required**: Shows placement recommendation and template; author must create the visual manually.
- **⚠️ Template mockup**: Shows a greyed-out example structure (not real extracted content).

**Note**: Recommendations with generation confidence below 60% display a warning: *"Auto-generated content is weak for this case. Use the placement hint and draft the visual manually."* Even if auto-generation is available, the placement hint is always trustworthy.

## Understanding Recommendations

### Confidence Tiers Explained

Each recommendation displays two independent confidence scores:

#### Placement Confidence (Teal %)
Estimates how reliably the tool identified *where* a visual belongs in your document.

- **95–98%**: Anchored to a specific procedure step (e.g., "Insert after step 3: Verify tenant status").
- **90–95%**: Anchored to a section context (e.g., "Before the Configuration Steps section").
- **70–89%**: High-quality heuristic match (e.g., multiple keyword triggers and strong signal correlation).
- **35–69%**: Lower-confidence match (e.g., one keyword trigger or ambiguous context).

**Interpretation**: Even at 35%, a placement recommendation is usually sound—the tool identified a reasonable spot for a visual. Trust this tier.

#### Generation Confidence (Amber %)
Estimates whether auto-generated visual *content* is trustworthy enough to use as a draft.

- **80–100%**: Strong signals; auto-generated content should be immediately usable or require minimal editing.
- **60–79%**: Moderate signals; content is a reasonable draft but may need refinement for accuracy or completeness.
- **40–59%**: Weak signals; content requires significant revision or manual reauthoring.
- **0–39%**: Very weak or disabled; content should not be trusted; manual authoring is strongly recommended.
- **0% (Decision Trees, Illustrations, GIF Tutorials)**: Auto-generation is disabled. Show a greyed-out template for reference only.

**Interpretation**: If generation confidence is below 60%, use the placement hint to manually author the visual instead of trying to refine weak auto-generated content.

### Rule Traces: Why Each Recommendation Fired

Every recommendation includes a "Why this recommendation fired" section that breaks down the reasoning into four components:

1. **Rule that fired** — The UI shows a human-readable rule name first, such as "Multi-Step Workflow Rule," with the internal ID (for example `PR_WORKFLOW`) underneath for cross-reference.
2. **Placement confidence reasoning** — Explains which placement heuristic was applied and why (e.g., "Anchored to section context before task execution (90%)").
3. **Generation confidence reasoning** — Explains which signals were found and how they scored (e.g., "3 procedural steps detected; 80% signal strength for flowchart generation").
4. **Worthiness score** — A quick 1–10 summary of how compelling the evidence is (e.g., "Worthiness: 8/10").
5. **Primary signal evidence** — Lists the concrete signals that triggered the rule (e.g., "Signals: 4 sequential steps, 2 conditional branches, 1 verification gate").

Before the bullet trace, each card now shows a short rule summary block with:

- **Display name** — Plain-English rule name the writer can understand immediately
- **Internal ID** — Secondary label for maintainers and power users
- **Trigger summary** — One sentence describing what the rule checks for
- **Expandable definition** — Additional rule detail plus the target visual type and reader question

**Example trace:**
```
Why this recommendation fired

Multi-Step Workflow Rule
PR_WORKFLOW · Python reasoning rule
Fires when 4 or more sequential procedure steps are detected and the reader needs the full sequence.

• Placement confidence: 95% (Anchored to specific step "After input validation")
• Generation confidence: 72% (Clear linear flow, 4 steps, minor ambiguity in error handling)
• Worthiness score: 8/10 (Strong procedural structure)
• Signals: 4 sequential steps, 1 warning note, 1 verification step
```

This transparent approach replaces opaque "confidence %" with legible reasoning, so you can decide whether to trust the recommendation or override it.

### Rule Glossary

The application guide includes an in-app rule glossary so writers can look up any rule name without reading source code. The current catalog includes:

- **System Relationships Rule** (`PR_CONNECTIONS`) — Fires when the section describes explicit relationships or data movement between components
- **UI Navigation Rule** (`PR_SCREENSHOT`) — Fires when the section contains dense, step-by-step UI actions that readers should see on screen
- **Multi-Step Workflow Rule** (`PR_WORKFLOW`) — Fires when 4 or more sequential procedure steps are detected and the reader needs the full sequence
- **Branching Decision Rule** (`PR_DECISION`) — Fires when the section contains real reader choices, such as if/else branches or named option comparisons
- **File Transfer Workflow Rule** (`VR006`) — Fires when the section mentions import or export actions that imply a repeatable file-transfer workflow
- **Field Mapping Rule** (`VR013`) — Fires when the section describes source-to-target field mappings, data types, or tag mapping vocabulary
- **Physical Setup Illustration Rule** (`VR005`) — Fires when the section describes physical installation tasks such as mounting, cabling, or power wiring
- **Structured Configuration Example Rule** (`VR007`) — Fires when the section contains code-like configuration content such as JSON, YAML, or XML examples

## Getting Started

### Prerequisites

- **Python 3.8+** (tested on 3.11.9)
- **Flask** for web serving
- **pip** package manager

### Installation

#### 1. Clone or download the repository

```bash
git clone <repository-url>
cd Doc-Visual-Intelligence
```

#### 2. Create a virtual environment (recommended)

```bash
# On Windows
python -m venv .venv
.venv\Scripts\activate

# On macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- Flask (web framework)
- Any document parsing libraries (if used; current version supports plain text, Markdown, and JSON)

### Running Locally

#### Start the application

```bash
# On Windows
.venv\Scripts\python.exe app.py

# On macOS/Linux
python3 app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5000
 * Press CTRL+C to quit
```

#### Open the web interface

Navigate to **`http://127.0.0.1:5000`** in your web browser.

#### Analyze a document

1. Paste or load sample documentation text into the text area.
2. Click **"Analyze"** to run the detection engine.
3. Review recommendations grouped by section.
4. For each recommendation:
   - **Read the placement confidence** (teal %) to understand *where* a visual belongs.
   - **Check the generation confidence** (amber %) to see if auto-generated content is trustworthy.
   - **Expand "Why this recommendation fired"** to see the rule trace explaining the reasoning.
   - For low generation confidence or manual visual types (Decision Tree), use the placement hint to author the visual manually.

## Desktop Application (PySide6)

The desktop edition keeps the same analyzer pipeline while running fully local on the user machine. No cloud upload path is required.

### Why this packaging path

- Native desktop UX for document open/analyze workflows
- Local-only operation aligned with privacy posture
- Reuses the existing rule engine and generators
- Supports internal enterprise distribution as a signed executable package

### Running desktop mode from source

1. Install desktop dependencies:

```bash
# On Windows
.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt

# On macOS/Linux
python3 -m pip install -r requirements-desktop.txt
```

2. Launch the desktop app:

```bash
# On Windows
.venv\Scripts\python.exe desktop/main.py

# On macOS/Linux
python3 desktop/main.py
```

3. In the UI:

- Click **Open Document** and select `.txt`, `.md`, `.json`, `.pdf`, or `.docx`
- Click **Analyze** to run section splitting and visual detection
- Review section-level recommendations with confidence split and rule trace
- Click **Verify Privacy** for local privacy posture confirmation

### Packaging for distribution

#### Windows build

```powershell
./desktop/build_windows.ps1
```

Build output:

- `dist/DocVisualAdvisor/DocVisualAdvisor.exe`

#### macOS/Linux build

```bash
chmod +x ./desktop/build_unix.sh
./desktop/build_unix.sh
```

Build output:

- `dist/DocVisualAdvisor/` bundle

### Enterprise rollout notes

- Sign the produced executable with your organization certificate before distribution
- Distribute through internal software channels (for example Intune, SCCM, Jamf)
- Keep `DVI_PRIVACY_MODE=1` as the enforced default for confidential use
- Validate each release with rule-coverage tests before packaging

### Configuration

#### Customize detection rules

Edit `rules/visual_rules.json` to add or modify rule triggers:

```json
{
  "id": "VR_CUSTOM",
  "keywords": ["trigger_word_1", "trigger_word_2"],
  "min_steps": 2,
  "min_words": 50,
  "weight": 1.0,
  "visual_type": "Flowchart",
  "reason": "Custom reason shown in results"
}
```

Supported fields:
| Field         | Type   | Description                                    |
|---------------|--------|------------------------------------------------|
| `id`          | string | Unique rule identifier                         |
| `keywords`    | array  | List of trigger words to match in content      |
| `min_steps`   | int    | Minimum procedure steps required to activate   |
| `min_words`   | int    | Minimum word count required to activate        |
| `weight`      | float  | Multiplier applied to keyword match score      |
| `visual_type` | string | The recommended visual type (see table above)  |
| `reason`      | string | Explanation shown in the results               |

#### Entity normalization

Edit `rules/knowledge_model.json` to define canonical entities and aliases:

```json
{
  "canonical": "Controller",
  "aliases": ["PLC", "S7-1500", "CPU", "microcontroller"]
}
```

This prevents graph fragmentation when the same component is referred to by multiple names.

## Troubleshooting

### Common Issues

#### The app won't start (Port 5000 already in use)

**Problem**: Error message like "Address already in use" when running `app.py`.

**Solution**: 
- Stop any other Flask or Python processes using port 5000.
- Or, modify the port in `app.py`:
  ```python
  if __name__ == '__main__':
      app.run(debug=True, port=5001)  # Use a different port
  ```

#### No recommendations appear for my document

**Problem**: Uploaded a document but got no visual recommendations.

**Possible causes**:
- Section headings not detected (the splitter requires explicit heading markers like `##` or `###`).
- Content doesn't match any rule keywords.
- Document is too short or too generic.

**Solutions**:
- Ensure your document has clear section headings (Markdown style: `## Section Name`).
- Use specific technical keywords that align with the rules in `visual_rules.json` (e.g., "click button", "configure", "PLC", "if...else").
- Check the browser console (F12 → Console) for any error messages.

#### Decision Tree recommendation shows only a greyed-out template

**Problem**: The decision tree section shows a faded "Example Structure" with generic labels.

**Expected behavior**: This is correct! Auto-generation for decision trees is disabled because conditional extraction is unreliable. The greyed-out template is intentionally a *placeholder* to show you what type of visual belongs there. Use the placement hint to author the tree manually.

#### Generated visual looks wrong or incomplete

**Problem**: A screenshot, flowchart, or architecture diagram was generated but contains incorrect content or missing elements.

**Check the generation confidence**:
- If generation confidence is below 60%, a warning appears: "Auto-generated content is weak for this case."
- Use the placement hint and manually author the visual instead.

**Improve the input**:
- Add more explicit relationships or steps to the section (e.g., "Component A sends data to Component B" for architecture diagrams).
- Use keywords that clearly indicate the visual type (e.g., "click", "select", "configure" for screenshots).

#### Rule X isn't triggering for my section

**Problem**: Expected a recommendation but got none, or got a different visual type.

**Debugging**:
1. Check which rules are active in `rules/visual_rules.json`.
2. Verify that your section text contains keywords defined in the rule.
3. If the rule requires a minimum step count (`min_steps`), ensure your section has that many steps.
4. Review the rule's `weight` — lower-weight rules may be suppressed by higher-scoring matches.

**Test a simple example**:
```
## Configure the System

1. Open the settings menu.
2. Enter the IP address.
3. Click Save.
```
This should trigger a Flowchart recommendation (3 steps detected).

## Frequently Asked Questions (FAQ)

### How do I know if a recommendation is trustworthy?

**Look at the confidence tiers**:
- **Placement confidence (teal %)**: 90%+ means the location is almost certainly correct. Even 50%+ is usually sound—the tool found a reasonable spot.
- **Generation confidence (amber %)**: 70%+ means auto-generated content is mostly usable. Below 60% means manual authoring is recommended.

Always trust the placement. Verify the content quality through generation confidence.

### Why does my Decision Tree show a template instead of the actual extracted tree?

Decision trees require extracting conditional branches from natural language, which is highly error-prone. Rather than show unreliable output, the tool shows a template to indicate *where* a decision tree belongs, and recommends manual authoring.

You can see the placement is sound (90–98% confidence) but generation is disabled (0% confidence). Use the placement hint to position your manually-authored tree.

### Can I disable certain visual types from being recommended?

Yes. Edit `rules/visual_rules.json` and:
- **Delete** the entire rule object to disable a visual type entirely.
- **Comment out** keywords within a rule to reduce its trigger frequency.
- **Increase** the `min_steps` or `min_words` threshold to raise the bar for recommendations.

### Can I customize the generated visual content?

For SVG flowcharts and architecture diagrams: you can download the SVG and edit it in any vector editor (Inkscape, Adobe Illustrator, or online tools).

For other visual types (screenshots, illustrations, GIF tutorials): the generated content is a mockup. Use it as a reference and create the final visual in your preferred tool.

### How often is the tool updated?

The tool is based on static rules in `rules/visual_rules.json` and the entity model in `rules/knowledge_model.json`. Updates require manual rule edits. No automatic ML retraining is performed—this is intentional to maintain transparency and control.

### Can the tool work with DOCX, PDF, or other formats?

Yes. The current extractor supports `.txt`, `.md`, `.json`, `.pdf`, and `.docx` directly.

If you need more formats:
1. Extend `analyzers/text_extractor.py` with another parser.
2. Add the new extension to file-open filters in desktop and web flows.
3. Add regression tests for extraction limits and parser safety.

### Is there an API or command-line interface?

Currently, the tool is web-based only. To access recommendations programmatically:
1. Import `visual_detector.py` and call `detect_visuals(section_title, section_content)` directly.
2. Or, extend `app.py` to expose a JSON API endpoint.

Example:
```python
from analyzers.visual_detector import detect_visuals
recommendations = detect_visuals("Installation Steps", "1. Download... 2. Extract... 3. Run...")
for rec in recommendations:
    print(rec['visual_type'], rec['placement_confidence'], rec['generation_confidence'])
```

### How can I provide feedback or report a bug?

Create an issue in the repository with:
- The document section that caused the problem
- The recommendation you received
- What you expected instead
- Your confidence tier scores and rule trace (copy from the web UI)

## License

This project is provided as-is. Modify and distribute as needed for your technical documentation purposes.
