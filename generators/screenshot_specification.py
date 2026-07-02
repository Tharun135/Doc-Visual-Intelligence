"""
Screenshot Specification Generator — structured UI capture briefs.

Converts prose instructions into actionable screenshot specifications
that tell technical writers exactly what to capture and how to annotate.

Output format:
{
    "placement": "Before Step 3",
    "purpose": "Show the Upload dialog after clicking Upload.",
    "capture": {
        "include": ["Upload dialog", "Browse button", "ZIP file field"],
        "highlight": ["Upload button"],
        "exclude": ["Personal information", "File paths"],
        "crop": "Dialog only"
    },
    "checklist": [
        "Upload dialog is visible",
        "Browse button is visible",
        ...
    ],
    "annotations": [
        {"number": 1, "label": "Upload button", "position": "bottom-right"},
        ...
    ]
}
"""

import re
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class ScreenshotSpecification:
    placement: str  # "Before Step 3", "After clicking Upload", etc.
    capture_after: str  # Human-friendly timing, e.g., "After step 1: Select process"
    purpose: str  # Why this screenshot matters
    focus_area: str = ""  # Primary focus target in the screenshot
    capture_include: list[str] = field(default_factory=list)  # What UI to show
    capture_highlight: list[str] = field(default_factory=list)  # What to emphasize
    capture_exclude: list[str] = field(default_factory=list)  # What to hide/crop
    capture_crop: str = ""  # Cropping instruction ("Dialog only", "Window", etc.)
    crop_level: str = "Medium"  # Crop profile: Full page, Medium, Dialog only
    crop_guidance: str = ""  # Practical crop instruction text
    ui_elements: list[str] = field(default_factory=list)  # Must-show UI terms
    context_page: str = ""  # Documentation page context
    context_section: str = ""  # Documentation section context
    context_dialog: str = "None"  # Active dialog name if present
    checklist_items: list[str] = field(default_factory=list)  # Verification items
    annotations: list[dict] = field(default_factory=list)  # Callout suggestions

    def to_dict(self):
        required_elements = self.ui_elements if self.ui_elements else self.capture_include
        required_count = len(required_elements)
        return {
            "placement": self.placement,
            "capture_after": self.capture_after,
            "purpose": self.purpose,
            "focus_area": self.focus_area,
            "capture": {
                "include": self.capture_include,
                "highlight": self.capture_highlight,
                "exclude": self.capture_exclude,
                "crop": self.capture_crop,
            },
            "crop_recommendation": {
                "level": self.crop_level,
                "guidance": self.crop_guidance,
            },
            "ui_elements": self.ui_elements,
            "context": {
                "page": self.context_page,
                "section": self.context_section,
                "dialog": self.context_dialog,
            },
            "coverage": {
                "required_ui_elements": required_elements,
                "required_count": required_count,
                "covered_count": required_count,
                "coverage_display": f"{required_count} / {required_count}",
            },
            "checklist": self.checklist_items,
            "annotations": self.annotations,
        }


# UI element keywords and their typical properties
UI_ELEMENTS = {
    "dialog": {"type": "container", "keywords": ["dialog", "window", "modal", "popup", "panel"]},
    "button": {"type": "control", "keywords": ["button", "click", "press"]},
    "field": {"type": "input", "keywords": ["field", "input", "text box", "enter", "type"]},
    "dropdown": {"type": "input", "keywords": ["dropdown", "select", "menu", "choose"]},
    "checkbox": {"type": "input", "keywords": ["checkbox", "check", "uncheck"]},
    "tab": {"type": "navigation", "keywords": ["tab", "click on tab"]},
    "menu": {"type": "navigation", "keywords": ["menu", "right-click", "context menu"]},
    "form": {"type": "container", "keywords": ["form", "fill in", "submit"]},
    "table": {"type": "container", "keywords": ["table", "row", "column", "select row"]},
    "message": {"type": "feedback", "keywords": ["message", "notification", "alert", "warning", "error"]},
    "status": {"type": "feedback", "keywords": ["status", "progress", "loading"]},
}

# Elements to exclude by default
DEFAULT_EXCLUDES = [
    "personal information",
    "credentials",
    "passwords",
    "tokens",
    "api keys",
    "file paths",
    "user data",
    "notifications",
    "timestamps",
]


def _extract_ui_elements(text: str) -> dict[str, list[str]]:
    """Extract UI element names and actions from prose."""
    elements = {
        "dialogs": [],
        "buttons": [],
        "fields": [],
        "dropdowns": [],
        "checkboxes": [],
        "tabs": [],
        "menus": [],
        "forms": [],
        "tables": [],
        "messages": [],
        "actions": [],
    }

    text_lower = text.lower()

    # Extract quoted elements: "Upload", "Browse", etc.
    quoted = re.findall(r'"([^"]+)"', text)
    for q in quoted:
        q_lower = q.lower()
        # Classify each quoted element more carefully
        if any(kw in q_lower for kw in ["field", "box", "input", "path", "name", "email", "password", "key"]):
            elements["fields"].append(q)
        elif any(kw in q_lower for kw in ["dropdown", "select", "environment", "mode", "type"]):
            elements["dropdowns"].append(q)
        elif any(kw in q_lower for kw in ["checkbox", "toggle", "switch", "tick box"]):
            elements["checkboxes"].append(q)
        else:
            elements["buttons"].append(q)

    # Extract dialog/window references
    dialog_pattern = r"(?:the\s+)?([A-Z][A-Za-z0-9\s]*?)(?:\s+(?:dialog|window|panel|popup|modal|screen))"
    dialogs = re.findall(dialog_pattern, text)
    elements["dialogs"].extend(dialogs)

    # Extract button references by action (click, press, select) - but NOT from dialog pattern
    # Be more precise to avoid matching dialog names
    button_pattern = r"(?:click|press|tap)\s+(?:(?:the|on)\s+)?([A-Z][A-Za-z0-9\s]*?)(?:\s+button)?(?:[.,;]|$)"
    buttons = re.findall(button_pattern, text, re.IGNORECASE)
    elements["buttons"].extend(buttons)

    # Extract field references
    field_pattern = r"(?:enter|type|fill in|input|paste)\s+(?:(?:your|the)\s+)?([A-Z][A-Za-z0-9\s]*?)(?:\s+(?:field|box|input|area))?(?:[.,;]|$)"
    fields = re.findall(field_pattern, text, re.IGNORECASE)
    elements["fields"].extend(fields)

    # Extract dropdown/select references
    dropdown_pattern = r"(?:select|choose)\s+(?:(?:the|a)\s+)?\"?([A-Z][A-Za-z0-9\s]*)\"?"
    dropdowns = re.findall(dropdown_pattern, text, re.IGNORECASE)
    elements["dropdowns"].extend(dropdowns)

    # Extract checkbox/toggle references with explicit UI nouns to avoid
    # false positives like "check your permissions".
    checkbox_pattern = (
        r"\b(?:check|uncheck|toggle|enable|disable)\b\s+"
        r"(?:the\s+)?\"?([A-Za-z][A-Za-z0-9\s\-/]{1,60})\"?\s+"
        r"(?:checkbox|option|toggle|switch)\b"
    )
    checkboxes = re.findall(checkbox_pattern, text, re.IGNORECASE)
    elements["checkboxes"].extend(checkboxes)

    # Extract table/panel references used in verification-style steps
    table_pattern = r"(?:from|in|on)\s+the\s+([A-Za-z][A-Za-z0-9\s\-/]{1,50})\s+(table|panel|grid)"
    table_refs = re.findall(table_pattern, text, re.IGNORECASE)
    for name, kind in table_refs:
        elements["tables"].append(f"{name.strip()} {kind.lower()}")

    if re.search(r"\btable\b|\bgrid\b|\brow\b", text_lower):
        if not elements["tables"]:
            elements["tables"].append("Process list table")

    # Track verification/state actions that often need screenshots even without explicit clicks.
    if re.search(r"\bverify\b|\bensure\b|\bconfirm\b|\bcheck\b|\breview\b|\bselected\b|\bselection\b", text_lower):
        elements["actions"].append("state verification")

    # Deduplicate and clean
    for key in elements:
        # Remove duplicates and very short matches
        cleaned = [item.strip() for item in set(elements[key]) if len(item.strip()) > 1]
        elements[key] = cleaned[:5]  # Limit to 5 per category

    return elements


def _build_capture_include(elements: dict[str, list[str]], context: str) -> list[str]:
    """Determine what should be included in the screenshot."""
    include = []

    # Always include primary container (dialog, form, window)
    if elements["dialogs"]:
        primary_dialog = elements["dialogs"][0]
        include.append(f"{primary_dialog} dialog")
    elif "form" in context.lower():
        include.append("Form with all fields")
    else:
        include.append("Main window or interface")

    # Include referenced UI controls (but don't duplicate dialog name)
    for button in elements["buttons"][:3]:
        if button.lower() not in (d.lower() for d in elements["dialogs"]):
            include.append(f"{button} button")

    for field in elements["fields"][:3]:
        include.append(f"{field} field")

    for dropdown in elements["dropdowns"][:2]:
        include.append(f"{dropdown} dropdown")

    for checkbox in elements["checkboxes"][:2]:
        include.append(f"{checkbox} checkbox")

    for table in elements["tables"][:2]:
        include.append(table)

    has_selection_context = bool(
        elements["tables"]
        or re.search(r"\bselected\b|\bselection\b|\brow\b|\btable\b|\bgrid\b", context, re.IGNORECASE)
    )
    if has_selection_context and not any("selected" in item.lower() for item in include):
        include.append("Selected row state")

    return include


def _build_capture_highlight(elements: dict[str, list[str]], text: str) -> list[str]:
    """Determine what should be highlighted/annotated."""
    highlight = []

    # Highlight the primary action button (usually first "click" mentioned)
    click_pattern = r"(?:click|press)\s+(?:(?:the|on)\s+)?([A-Z][A-Za-z0-9\s]*?)(?:\s+button)?"
    clicks = re.findall(click_pattern, text, re.IGNORECASE)
    if clicks:
        primary_click = clicks[0].strip()
        if len(primary_click) > 1:
            highlight.append(f"{primary_click} button")

    # Highlight newly filled/selected fields
    if any(kw in text.lower() for kw in ["enter", "type", "fill"]):
        if elements["fields"]:
            highlight.append(f"{elements['fields'][0]} field")

    # Highlight selected items from dropdowns
    if any(kw in text.lower() for kw in ["select", "choose"]):
        if elements["dropdowns"]:
            highlight.append(f"{elements['dropdowns'][0]} dropdown")

    # Highlight table row selection for validation steps
    if re.search(r"\bselected\b|\bselect\b", text, re.IGNORECASE) and elements["tables"]:
        highlight.append("Selected process row")

    if not highlight and elements["tables"]:
        highlight.append("Selected process row")

    return highlight[:2]  # Limit to 2 callouts


def _build_capture_exclude() -> list[str]:
    """Standard exclusions for all screenshots."""
    return DEFAULT_EXCLUDES.copy()


def _build_checklist(elements: dict[str, list[str]], include: list[str], highlight: list[str]) -> list[str]:
    """Generate verification checklist for the screenshot."""
    checklist = []

    # Container visibility
    if elements["dialogs"]:
        dialog_name = elements["dialogs"][0]
        checklist.append(f"□ {dialog_name} dialog is visible")
    else:
        checklist.append("□ Main window/interface is visible")

    # Key UI element visibility (just the most important ones)
    if elements["buttons"]:
        checklist.append(f"□ {elements['buttons'][0]} button is visible")
    if elements["fields"]:
        checklist.append(f"□ {elements['fields'][0]} field is visible")
    if elements["tables"]:
        checklist.append(f"□ {elements['tables'][0]} is visible")

    # Annotation visibility (if highlighting)
    if highlight:
        primary_highlight = highlight[0].replace(" button", "").replace(" field", "")
        checklist.append(f"□ {primary_highlight} is prominently visible")

    # Standard checks
    checklist.append("□ No personal information visible")
    checklist.append("□ No error messages or warnings")
    checklist.append("□ Image is clear and readable")

    return checklist


def _build_annotations(elements: dict[str, list[str]], highlight: list[str]) -> list[dict]:
    """Generate suggested callouts."""
    annotations = []

    # Number the highlighted elements
    for i, item in enumerate(highlight, start=1):
        # Extract element name
        name = item.replace(" button", "").replace(" field", "").replace(" dropdown", "")
        annotations.append({
            "number": i,
            "label": name,
            "position": "bottom-right" if i == 1 else "top-right",
        })

    return annotations


def _infer_context(section_title: str, step_context: str, elements: dict[str, list[str]]) -> tuple[str, str, str]:
    """Infer documentation-friendly page, section, and dialog context."""
    page = section_title.strip() if section_title and section_title.strip() else "Current page"

    section_match = re.search(
        r"(?:from|in|on)\s+the\s+([A-Za-z][A-Za-z0-9\s\-/]{1,50})\s+(table|panel|section|tab)",
        step_context,
        re.IGNORECASE,
    )
    if section_match:
        section = f"{section_match.group(1).strip()} {section_match.group(2).lower()}"
    elif elements["tables"]:
        inferred = elements["tables"][0].strip()
        if re.search(r"\b(table|panel|section|tab|grid)\b$", inferred, re.IGNORECASE):
            section = inferred
        else:
            section = f"{inferred} table"
    else:
        section = "Main work area"

    dialog = elements["dialogs"][0].strip() if elements["dialogs"] else "None"
    return page, section, dialog


def _build_crop_recommendation(include: list[str], elements: dict[str, list[str]]) -> tuple[str, str, str]:
    """Return crop level, user guidance, and short crop label."""
    if elements["dialogs"]:
        return (
            "Dialog only",
            "Capture only the active dialog and its direct action controls.",
            "Dialog only",
        )

    include_lower = " ".join(include).lower()
    if "table" in include_lower or "panel" in include_lower:
        return (
            "Medium",
            "Capture only the relevant panel with adjacent action controls.",
            "Panel-level crop",
        )

    if len(include) >= 6:
        return (
            "Full page",
            "Capture the full page to preserve navigation and context.",
            "Full page",
        )

    return (
        "Medium",
        "Capture the active work area and keep unrelated sidebars out of frame.",
        "Active work area",
    )


def _build_ui_elements(include: list[str], highlight: list[str]) -> list[str]:
    items = []
    for item in include + highlight:
        item = item.strip()
        if item and item not in items:
            items.append(item)
    return items[:8]


def generate_screenshot_specification(
    step_context: str,
    placement: str,
    step_number: int,
    section_title: str = "",
    placement_text: str = "",
) -> Optional[ScreenshotSpecification]:
    """
    Generate a screenshot specification from step context.

    Args:
        step_context: Text of the step (e.g., "Click Upload. Browse to the ZIP file.")
        placement: When to take screenshot ("Before", "After", etc.)
        step_number: Which step (1, 2, 3, etc.)
        section_title: Context about the overall task

    Returns:
        ScreenshotSpecification object or None if no UI elements detected
    """
    # Early exit if minimal content
    if not step_context or len(step_context) < 10:
        return None

    # Extract UI elements
    elements = _extract_ui_elements(step_context)

    # Do not hard-fail when UI terms are sparse. Screenshot recommendations should still
    # produce a usable baseline specification for technical writers.

    # Build specification components
    include = _build_capture_include(elements, step_context)
    highlight = _build_capture_highlight(elements, step_context)
    exclude = _build_capture_exclude()
    checklist = _build_checklist(elements, include, highlight)
    annotations = _build_annotations(elements, highlight)

    # Determine crop recommendation and effective crop label
    crop_level, crop_guidance, crop = _build_crop_recommendation(include, elements)

    # Infer documentation context fields
    context_page, context_section, context_dialog = _infer_context(section_title, step_context, elements)

    # Aggregate required UI elements for checklists/coverage
    ui_elements = _build_ui_elements(include, highlight)

    # Capture timing
    capture_after = placement_text.strip() if placement_text and placement_text.strip() else f"{placement} step {step_number}"

    # Build purpose statement
    main_action = ""
    if "click" in step_context.lower():
        button = elements["buttons"][0] if elements["buttons"] else "a button"
        main_action = f"after clicking {button}"
    elif "fill" in step_context.lower() or "enter" in step_context.lower():
        field = elements["fields"][0] if elements["fields"] else "a field"
        main_action = f"after entering {field}"
    elif "select" in step_context.lower():
        main_action = "after selecting the option"
    elif (
        "verify" in step_context.lower()
        or "ensure" in step_context.lower()
        or "confirm" in step_context.lower()
        or "check" in step_context.lower()
        or "review" in step_context.lower()
    ):
        main_action = "while verifying the expected UI state"

    # Build purpose statement with the primary dialog/container
    if elements["dialogs"]:
        dialog_name = elements["dialogs"][0]
        purpose = f"Show the {dialog_name} dialog {main_action}." if main_action else f"Show the {dialog_name} dialog."
    else:
        purpose = f"Show the current state {main_action}." if main_action else "Show the active window."

    spec = ScreenshotSpecification(
        placement=f"{placement} Step {step_number}",
        capture_after=capture_after,
        purpose=purpose,
        focus_area=highlight[0] if highlight else (ui_elements[0] if ui_elements else "Primary action control"),
        capture_include=include,
        capture_highlight=highlight,
        capture_exclude=exclude,
        capture_crop=crop,
        crop_level=crop_level,
        crop_guidance=crop_guidance,
        ui_elements=ui_elements,
        context_page=context_page,
        context_section=context_section,
        context_dialog=context_dialog,
        checklist_items=checklist,
        annotations=annotations,
    )

    return spec
