r"""
Regression tests for rule metadata coverage and recommendation payload integrity.

Run with:
    .venv\Scripts\python.exe -m pytest tests/test_rule_coverage.py -v

These tests exist because opaque rule IDs leaked to the UI before, and we need
CI enforcement to prevent a silent regression if detect_visuals() is modified.
"""
import pytest
from analyzers.visual_detector import detect_visuals, get_rule_catalog
from rules.rule_definitions import PYTHON_RULES


# ─────────────────────────────────────────────────────────────
# SDEX / licence document that historically produced broken output.
# We don't assert specific visual types here (the engine's logic
# may change), but every recommendation must carry a full, human-
# readable rule_summary — that's the invariant we're protecting.
# ─────────────────────────────────────────────────────────────
SDEX_PURCHASING_TEXT = """\
## Purchasing Licenses

Before activating Industrial Edge Management (IEM), you must obtain the correct
license. Different license tiers are available depending on the number of devices
you intend to manage and the features you require.

1. Log in to the SIEMENS Industry Mall.
2. Search for "Industrial Edge Management" and select the correct product variant.
3. Add the license to your cart and complete the purchase.
4. Check your email for the license confirmation. If the license email has not
   arrived within 24 hours, contact the Siemens support portal.
5. Download the license file from the Industry Mall order confirmation page.
6. Store the license file in a secure location; you will need it during activation.

If your tenant already has a paid plan, skip to the Activation section.
If not, select the basic subscription as the baseline option, then proceed
to request an upgrade. Alternatively, contact your Siemens account manager
to negotiate a volume license.
"""

ARCH_TEXT = """\
## System Overview

The Industrial Edge Device (IED) connects to the Industrial Edge Hub via OPC UA.
The Edge Hub publishes collected tag values to the MQTT broker. The MQTT broker
forwards messages to the Cloud Connector, which routes data to the MindSphere backend.
"""
# Note: ARCH_TEXT must be long enough to pass the worthiness gate (word_count and
# relationship signals must be above the minimum threshold).  Keep it realistic.
ARCH_TEXT = """\
## System Overview

The Industrial Edge solution consists of several interconnected components that form
a complete data acquisition and cloud forwarding pipeline.

The Industrial Edge Device (IED) connects to the Industrial Edge Hub via OPC UA.
The Edge Hub publishes collected tag values to the MQTT broker. The MQTT broker
forwards messages to the Cloud Connector. The Cloud Connector routes data to the
MindSphere backend for long-term storage and analytics processing.

The PLC communicates with the IED over Profinet. The IED sends tag values to the
Edge Hub every 500 ms. The gateway bridges the OT and IT networks.
"""

WORKFLOW_TEXT = """\
## Installing the Connector

1. Open the Industrial Edge Management portal.
2. Navigate to the App Catalog.
3. Search for the SIMATIC S7 Classic Connector.
4. Click Install and confirm the dialog.
5. Wait for the installation to complete. Verify the status shows "Running".
6. Open the connector configuration and enter the PLC IP address.
7. Click Save to apply the configuration.
"""


# ─────────────────────────────────────────────────────────────
# Catalog completeness assertions
# ─────────────────────────────────────────────────────────────

def test_all_catalog_rules_have_display_name():
    """Every rule in get_rule_catalog() must have a non-empty display_name.

    Prevents raw IDs like 'PR_WORKFLOW' reaching the UI.
    """
    catalog = get_rule_catalog()
    assert catalog, "Rule catalog is empty"
    missing = [r["id"] for r in catalog if not r.get("display_name", "").strip()]
    assert not missing, f"Rules missing display_name: {missing}"


def test_all_catalog_rules_have_trigger_summary():
    """Every rule must have a one-sentence trigger_summary for the trace UI."""
    catalog = get_rule_catalog()
    missing = [r["id"] for r in catalog if not r.get("trigger_summary", "").strip()]
    assert not missing, f"Rules missing trigger_summary: {missing}"


def test_all_catalog_rules_have_trigger_criteria():
    """Every rule must have at least one trigger_criteria entry.

    This enforces that writers can answer 'would this fire if I changed X?'
    by reading the rule card — the root concern that motivated this fix.
    """
    catalog = get_rule_catalog()
    missing = [r["id"] for r in catalog if not r.get("trigger_criteria")]
    assert not missing, f"Rules missing trigger_criteria: {missing}"


def test_python_rules_have_metadata():
    """Python Rule dataclass instances must expose all metadata fields."""
    required_fields = {"id", "display_name", "trigger_summary", "trigger_criteria",
                       "description", "reader_question", "visual_type"}
    for rule in PYTHON_RULES:
        rule_dict = vars(rule)
        for field in required_fields:
            assert field in rule_dict and getattr(rule, field), (
                f"Rule {rule.id} missing or empty field: {field}"
            )


# ─────────────────────────────────────────────────────────────
# Recommendation payload assertions
# ─────────────────────────────────────────────────────────────

def _real_recommendations(title: str, text: str) -> list[dict]:
    """Return only recommendations that are not 'No recommendation'."""
    return [r for r in detect_visuals(title, text) if r["visual_type"] != "No recommendation"]


def test_recommendation_payload_includes_rule_summary_python_rule():
    """Python-rule recommendations must include a populated rule_summary dict."""
    recs = _real_recommendations("Installing the Connector", WORKFLOW_TEXT)
    assert recs, "Expected at least one recommendation for WORKFLOW_TEXT"
    for rec in recs:
        summary = rec.get("rule_summary")
        assert summary is not None, f"Missing rule_summary on {rec['visual_type']}"
        assert summary.get("display_name"), f"Empty display_name in rule_summary for {rec['visual_type']}"
        assert summary.get("trigger_summary"), f"Empty trigger_summary for {rec['visual_type']}"
        assert summary.get("trigger_criteria"), f"Empty trigger_criteria for {rec['visual_type']}"
        assert summary.get("id"), f"Missing rule id in rule_summary for {rec['visual_type']}"


def test_recommendation_payload_includes_rule_summary_json_rule():
    """JSON keyword-rule recommendations must also include a populated rule_summary dict."""
    import_text = (
        "To migrate your tag configuration, export tags from the source system "
        "by selecting File > Export tags. Save the exported file. Then import the "
        "file into the target system using File > Import file."
    )
    recs = _real_recommendations("Tag Migration", import_text)
    json_recs = [r for r in recs if r.get("source", "").startswith("json:")]
    if not json_recs:
        pytest.skip("No JSON-rule recommendations fired for this text; adjust sample if rules change")
    for rec in json_recs:
        summary = rec.get("rule_summary")
        assert summary is not None, f"Missing rule_summary on JSON-rule recommendation {rec['visual_type']}"
        assert summary.get("display_name"), f"JSON rule_summary missing display_name for {rec['visual_type']}"
        assert summary.get("trigger_criteria"), f"JSON rule_summary missing trigger_criteria for {rec['visual_type']}"


# ─────────────────────────────────────────────────────────────
# SDEX regression: the document that historically broke
# ─────────────────────────────────────────────────────────────

def test_sdex_purchasing_no_recommendation_carries_no_rule_summary():
    """No-recommendation entries must not pretend to carry rule metadata."""
    recs = detect_visuals("Purchasing Licenses", SDEX_PURCHASING_TEXT)
    for rec in recs:
        if rec["visual_type"] == "No recommendation":
            assert not rec.get("rule_summary"), (
                "No-recommendation entry should not carry a rule_summary"
            )


def test_sdex_purchasing_real_recs_have_full_rule_summary():
    """Any real recommendation on the SDEX text must have a full rule_summary.

    This is the regression guard for the original bug: raw IDs in traces.
    """
    recs = _real_recommendations("Purchasing Licenses", SDEX_PURCHASING_TEXT)
    for rec in recs:
        summary = rec.get("rule_summary")
        assert summary is not None, (
            f"SDEX regression: {rec['visual_type']} recommendation is missing rule_summary"
        )
        assert summary.get("display_name"), (
            f"SDEX regression: {rec['visual_type']} has empty display_name — raw ID would show in UI"
        )
        assert summary.get("trigger_criteria"), (
            f"SDEX regression: {rec['visual_type']} has no trigger_criteria — writer cannot falsify the rule"
        )


def test_sdex_purchasing_decision_tree_generation_confidence_is_zero():
    """Decision Tree recommendations on the SDEX text must always have generation_confidence=0."""
    recs = _real_recommendations("Purchasing Licenses", SDEX_PURCHASING_TEXT)
    decision_recs = [r for r in recs if r["visual_type"] == "Decision Tree"]
    for rec in decision_recs:
        assert rec["generation_confidence"] == 0, (
            "Decision Tree generation_confidence must be 0 (auto-generation disabled)"
        )
        assert rec["generated_artifact"] is None, (
            "Decision Tree generated_artifact must be None (auto-generation disabled)"
        )


def test_sdex_purchasing_generation_confidence_reasons_are_signal_grounded():
    """Generation confidence reasons must reference actual signal values, not generic phrases."""
    forbidden_generic_phrases = [
        "generation uses a",
        "generation is backed by",
        "generation is available",
    ]
    recs = _real_recommendations("Purchasing Licenses", SDEX_PURCHASING_TEXT)
    for rec in recs:
        reason = rec.get("generation_confidence_reason", "").lower()
        for phrase in forbidden_generic_phrases:
            assert phrase not in reason, (
                f"Generation confidence reason for {rec['visual_type']} still uses generic phrase: '{phrase}'. "
                f"Full reason: {rec['generation_confidence_reason']}"
            )


def test_arch_generation_confidence_references_relationship_count():
    """Architecture recommendations must cite the actual relationship count in their confidence reason."""
    recs = _real_recommendations("System Overview", ARCH_TEXT)
    arch_recs = [r for r in recs if r["visual_type"] in
                 {"Architecture Diagram", "Topology Diagram", "Data Flow Diagram", "Sequence Diagram"}]
    assert arch_recs, "Expected at least one architecture recommendation for ARCH_TEXT"
    for rec in arch_recs:
        reason = rec.get("generation_confidence_reason", "")
        # Should contain a digit (the relationship count) — proves it's signal-grounded
        assert any(c.isdigit() for c in reason), (
            f"Architecture generation_confidence_reason does not reference a signal count: '{reason}'"
        )


def test_workflow_generation_confidence_references_step_count():
    """Workflow recommendations must cite the actual step count in their confidence reason."""
    recs = _real_recommendations("Installing the Connector", WORKFLOW_TEXT)
    workflow_recs = [r for r in recs if r["visual_type"] in
                     {"Workflow Diagram", "Flowchart", "Sequence Diagram"}]
    assert workflow_recs, "Expected at least one workflow recommendation for WORKFLOW_TEXT"
    for rec in workflow_recs:
        reason = rec.get("generation_confidence_reason", "")
        assert any(c.isdigit() for c in reason), (
            f"Workflow generation_confidence_reason does not reference a signal count: '{reason}'"
        )
