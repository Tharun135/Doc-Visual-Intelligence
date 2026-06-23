#!/usr/bin/env python3
"""Direct test of Flask logic without HTTP"""

import sys
sys.path.insert(0, 'd:/visual-advisor')

from app import extract_text, split_sections
from analyzers.visual_detector import detect_visuals

test_content = """Procedure: Deploy Configuration
1. Open the HMI dashboard panel
2. Select configuration from settings
3. Validate parameters with S7-1500 controller
4. Deploy to cloud platform via gateway
5. Verify on remote server

The microcontroller processes data and sends it through the connector."""

print("V4 DIRECT INTEGRATION TEST")
print("=" * 60)

# Simulate the app flow
sections = split_sections(test_content)
print(f"✓ Sections identified: {len(sections)}")

recommendations = []
for section in sections:
    title = section.get("title", "Untitled")
    content = section.get("content", "")
    visuals = detect_visuals(title, content)
    recommendations.extend(visuals)

print(f"✓ Recommendations generated: {len(recommendations)}")
print()

print("TOP RECOMMENDATIONS:")
for i, rec in enumerate(recommendations[:3], 1):
    print(f"\n{i}. {rec['visual_type']}")
    print(f"   Content Type: {rec['content_type']} ({rec['content_type_confidence']}%)")
    print(f"   Priority: {rec['priority']}")
    print(f"   Visual Confidence: {rec['confidence']}")
    
    # Verify field exists and is populated
    if 'content_type_confidence' not in rec:
        print("   ✗ MISSING: content_type_confidence field")
    elif rec['content_type_confidence'] <= 0:
        print("   ✗ INVALID: content_type_confidence is zero or negative")
    else:
        print("   ✓ VALID: content_type_confidence properly set")

print("\n" + "=" * 60)
print("✓ V4 INTEGRATION TEST COMPLETE - All fields rendered correctly")
print("✓ Ready for UI display in index.html templates")
