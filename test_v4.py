#!/usr/bin/env python3
"""V4 Smoke Test - Entity Normalization and Content-Type Confidence"""

from analyzers.visual_detector import detect_visuals, extract_entities, classify_content, compute_signals

print("=" * 60)
print("V4 IMPLEMENTATION VALIDATION")
print("=" * 60)

# Test 1: Entity Canonicalization
print("\n1. ENTITY NORMALIZATION TEST")
print("-" * 60)
content_test1 = (
    "The S7-1500 controller communicates with the HMI panel "
    "and cloud platform through the gateway."
)
entities = extract_entities(content_test1)
print(f"Input: {content_test1}")
print(f"Detected entities (canonical): {entities}")
expected = {"Controller", "UI Component", "External System", "Gateway"}
detected = set(entities)
if detected == expected:
    print("✓ PASS: All aliases correctly normalized to canonical names")
else:
    print(f"⚠ Detected: {detected}, Expected: {expected}")

# Test 2: Content-Type Confidence Scoring
print("\n2. CONTENT-TYPE CONFIDENCE TEST")
print("-" * 60)
content_test2 = """Procedure: Configure the System
1. Select Import option from Settings menu
2. Choose configuration file
3. Validate parameters
4. Save settings
5. Verify deployment status

The system requires at least one microcontroller."""

title_test2 = "Configuration Procedure"
signals = compute_signals(content_test2)
content_type, confidence = classify_content(title_test2, content_test2, signals)
print(f"Title: {title_test2}")
print(f"Steps detected: {signals['steps']}")
print(f"Content type: {content_type}")
print(f"Confidence: {confidence}%")
if content_type == "Procedure" and confidence >= 85:
    print("✓ PASS: High-confidence Procedure classification")
else:
    print(f"⚠ Expected Procedure (≥85%), got {content_type} ({confidence}%)")

# Test 3: Full Recommendation Pipeline with Confidence
print("\n3. FULL PIPELINE TEST (with confidence)")
print("-" * 60)
recommendations = detect_visuals(title_test2, content_test2)
first_rec = recommendations[0]
print(f"Top recommendation: {first_rec['visual_type']}")
print(f"Content type: {first_rec['content_type']} ({first_rec['content_type_confidence']}%)")
print(f"Priority: {first_rec['priority']}")
print(f"Visual confidence: {first_rec['confidence']}")

has_confidence = "content_type_confidence" in first_rec
has_positive_value = first_rec.get("content_type_confidence", 0) > 0
if has_confidence and has_positive_value:
    print("✓ PASS: content_type_confidence field present and populated")
else:
    print("✗ FAIL: content_type_confidence missing or zero")

# Test 4: Multiple Content Types
print("\n4. CONTENT-TYPE VARIANCE TEST")
print("-" * 60)

# Procedure variant
proc_content = "1. Open dialog\n2. Enter values\n3. Click Save"
_, proc_conf = classify_content("Config Steps", proc_content, compute_signals(proc_content))

# Troubleshooting variant
trouble_content = "Error E001: Connection failed. Check network. Verify firewall settings."
trouble_type, trouble_conf = classify_content("Troubleshoot", trouble_content, compute_signals(trouble_content))

# Architecture variant
arch_content = "System topology: Controller connects to Gateway, which bridges to Cloud and HMI."
arch_type, arch_conf = classify_content("Architecture", arch_content, compute_signals(arch_content))

print(f"Procedure confidence: {proc_conf}%")
print(f"Troubleshooting type: {trouble_type} ({trouble_conf}%)")
print(f"Architecture type: {arch_type} ({arch_conf}%)")

if proc_conf > 0 and trouble_conf > 0 and arch_conf > 0:
    print("✓ PASS: Multiple content types scored with varying confidence")
else:
    print("⚠ Some content types not properly scored")

print("\n" + "=" * 60)
print("V4 VALIDATION COMPLETE")
print("=" * 60)
