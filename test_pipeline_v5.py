import pytest
from analyzers.visual_detector import detect_visuals, compute_signals, classify_content, _is_visually_worthy

def test_worthiness_gate_rejects_simple_config():
    # A simple instruction that doesn't need a visual
    content = "Enter the IP address of the server in the field."
    results = detect_visuals("Config", content)
    
    assert len(results) == 1
    assert results[0]["visual_type"] == "No recommendation"
    assert results[0]["source"] == "worthiness_gate"

def test_pr001_architecture_diagram():
    # Concept describing a system
    content = "The PLC connects to the edge device. The edge device sends data to the cloud."
    # Make it long enough to pass worthiness gate (>20 words)
    content += " " + "This ensures all data is properly forwarded for analytics processing without latency." * 3
    results = detect_visuals("System Overview", content)
    
    # Should trigger PR001
    top = results[0]
    assert top["visual_type"] == "Architecture Diagram"
    assert top["reader_question"] == "What is this?"

def test_pr002_screenshot():
    # UI dense instructions
    content = "Click the Settings menu. Select the Network tab. Open the Advanced panel. Enter the configuration. Click Save."
    content += " " + "Please be sure to save all configurations before exiting this dialog to ensure network stability."
    results = detect_visuals("Navigation", content)
    
    top = results[0]
    assert top["visual_type"] == "Screenshot"
    assert top["reader_question"] == "Where do I click?"

def test_non_procedural_ui_text_does_not_force_screenshot():
    # Autostart-like narrative text with UI terms but no real procedural structure.
    content = (
        'Set a project to autostart mode by activating the "Enable Autostart" option. '
        "The autostart feature is beneficial when an application or IE Device is restarted. "
        'Launch the runtime home page and click "Enable Autostart" to set the selected project. '
        'To change autostart, select a different project and click "Enable Autostart" again. '
        'To disable it, select the project and click "Disable Autostart".'
    )
    results = detect_visuals("Enabling autostart", content)

    recommended_types = [r["visual_type"] for r in results]
    assert "Screenshot" not in recommended_types
    assert "GIF / Video Tutorial" not in recommended_types

def test_pr003_workflow_diagram():
    # Long procedure
    content = """
    1. First start the service.
    2. Then authenticate with the token.
    3. Retrieve the payload from the endpoint.
    4. Process the data locally.
    5. Upload the results to the database.
    6. Verify the upload succeeded.
    7. Close the connection.
    """
    results = detect_visuals("Data processing", content)
    
    top = results[0]
    assert top["visual_type"] == "Workflow Diagram"
    assert top["reader_question"] == "What happens next?"

def test_pr004_decision_tree():
    # If/else branching logic
    content = """
    If the connection succeeds, deploy the connector. 
    If the connection fails, verify the IP settings.
    Otherwise, contact support.
    """
    # Pad to pass worthiness
    content += " " + "This logic flow must be followed precisely to ensure the device functions as expected in all states."
    results = detect_visuals("Troubleshooting", content)
    
    top = results[0]
    assert top["visual_type"] == "Decision Tree"
    assert top["reader_question"] == "Which option should I choose?"

def test_pr005_topology_data_flow():
    # System topology with data transfer
    content = """
    The sensor sends data to the PLC.
    The PLC publishes the data to the MQTT broker.
    The MQTT broker forwards data to the Industrial Edge Hub.
    """
    content += " " + "All information is monitored in real time." * 5
    results = detect_visuals("Data Flow", content)
    
    top = results[0]
    # In V5, PR001 (Architecture) and PR005 (Data Flow) both match system descriptions highly.
    visuals_recommended = [r["visual_type"] for r in results]
    assert "Architecture Diagram" in visuals_recommended or "Data Flow Diagram" in visuals_recommended
    assert top["reader_question"] in ["What is this?", "How are things connected?"]

def test_json_rule_vr005_illustration():
    # Physical setup keywords
    content = "To mount the device, connect cable A to the power supply. Fasten the DIN rail."
    content += " " + "Ensure it is tightly secured before continuing." * 3
    results = detect_visuals("Physical Installation", content)
    
    top = results[0]
    assert top["visual_type"] == "Illustration"
    assert "json:VR005" in top["source"]

def test_signal_extraction():
    content = "If the value is high, click Stop. Else, click Continue."
    signals = compute_signals(content)
    assert signals["conditional_branches"] >= 2
    assert signals["ui_interactions"] >= 2
