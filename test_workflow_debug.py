#!/usr/bin/env python3
"""Debug why Workflow Diagram artifact isn't generating"""

from analyzers.visual_detector import detect_visuals

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

print("All recommendations:")
for i, r in enumerate(rec):
    print(f"\n{i}. {r['visual_type']}")
    print(f"   Confidence: {r['confidence']}")
    print(f"   Has artifact: {'generated_artifact' in r}")
    if r.get('generated_artifact'):
        print(f"   Artifact type: {r['generated_artifact'].get('artifact_type')}")
    else:
        print(f"   generated_artifact value: {r.get('generated_artifact')}")
    if i > 5:
        break

# Specifically look for Workflow
workflow = next((r for r in rec if r.get('visual_type') == 'Workflow Diagram'), None)
if workflow:
    print(f"\n✓ Found Workflow Diagram")
    if workflow.get('generated_artifact'):
        print("  Has artifact!")
        artifact = workflow['generated_artifact']
        mermaid = artifact.get('mermaid', '')
        print(f"  Mermaid lines: {len(mermaid.split(chr(10)))}")
        print(f"\n{mermaid}")
    else:
        print(f"  NO ARTIFACT (value={workflow.get('generated_artifact')})")
else:
    print(f"\n✗ No Workflow Diagram in recommendations")
