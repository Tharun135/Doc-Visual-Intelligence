#!/usr/bin/env python3
"""Debug: See what recommendations are actually generated"""

from analyzers.visual_detector import detect_visuals

# Test 1: Procedure
long_procedure = """# Configure Industrial Edge - Extended Setup

Procedure
1. Access the Industrial Edge portal.
2. Click Configuration menu.
3. Select Add Device.
4. Enter device name and ID.
5. Assign device location.
6. Select communication protocol.
7. Configure IP address and port.
8. Enable security settings.
9. Define data retention policy.
10. Set up backup schedule."""

rec = detect_visuals("Extended Edge Configuration", long_procedure)
print("PROCEDURE - All recommendations:")
for i, r in enumerate(rec[:5], 1):
    print(f"  {i}. {r['visual_type']} (confidence: {r['confidence']})")
    print(f"     Has artifact: {'generated_artifact' in r}")

# Test 2: Conditional
conditional = """# Deployment Decision

1. Test the connection to verify connectivity.
2. If the connection test succeeds:
   Deploy the connector to production.
3. If the connection test fails:
   Check network cable and IP settings."""

rec2 = detect_visuals("Decision Logic", conditional)
print("\nCONDITIONAL - All recommendations:")
for i, r in enumerate(rec2[:5], 1):
    print(f"  {i}. {r['visual_type']} (confidence: {r['confidence']})")
    print(f"     Has artifact: {'generated_artifact' in r}")
