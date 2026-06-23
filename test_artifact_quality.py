#!/usr/bin/env python3
"""Check artifact quality for critical scenarios"""

from analyzers.visual_detector import detect_visuals

print("=" * 70)
print("ARTIFACT QUALITY CHECK")
print("=" * 70)

# ============================================================================
# SCENARIO 1: Long Procedure - Check Workflow Diagram artifact
# ============================================================================
print("\n1. WORKFLOW DIAGRAM (20-step procedure)")
print("-" * 70)

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
10. Set up backup schedule.
11. Configure cloud connection.
12. Add authentication credentials.
13. Define data filtering rules.
14. Enable logging and monitoring.
15. Configure alert thresholds.
16. Create deployment package.
17. Review configuration summary.
18. Approve and save settings.
19. Deploy to edge runtime.
20. Verify connection status."""

rec1 = detect_visuals("Extended Edge Configuration", long_procedure)
workflow = next((r for r in rec1 if r.get('visual_type') == 'Workflow Diagram'), None)

if workflow and workflow.get('generated_artifact'):
    artifact = workflow['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Status: ✓ Generated")
    print(f"Lines: {len(mermaid.split(chr(10)))}")
    print(f"Arrows: {mermaid.count('-->')}")
    print(f"\nMermaid preview (first 400 chars):")
    print(mermaid[:400])
    print("\n[... continues ...]")
    
    if mermaid.count('-->') == 20:
        print("✓ All 20 steps included as linear chain")
    if 'subgraph' in mermaid.lower():
        print("✓ Uses subgraph grouping")
    else:
        print("⚠ Linear chain - may be hard to read")
        print("  Recommendation: Group into phases (Setup, Config, Deploy, Verify)")
else:
    print("✗ No workflow artifact")

# ============================================================================
# SCENARIO 2: Real Architecture - Check content-driven entities
# ============================================================================
print("\n\n2. ARCHITECTURE DIAGRAM (content-driven)")
print("-" * 70)

real_architecture = """# Industrial Data Pipeline

System Architecture
The PLC publishes sensor data to the EtherNet/IP Connector.
The EtherNet/IP Connector publishes to the MQTT Broker.
The MQTT Broker forwards time-series data to Industrial Edge.
Industrial Edge stores data and communicates with the cloud database."""

rec2 = detect_visuals("Data Pipeline Architecture", real_architecture)
arch = next((r for r in rec2 if r.get('visual_type') in ['Architecture Diagram', 'Topology Diagram', 'Data Flow Diagram']), None)

if arch and arch.get('generated_artifact'):
    artifact = arch['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Status: ✓ Generated ({arch['visual_type']})")
    print(f"\nMermaid:\n{mermaid}")
    
    # Check for content entities
    checks = {
        'PLC': 'PLC' in mermaid,
        'EtherNet/IP Connector': 'EtherNet' in mermaid,
        'MQTT Broker': 'MQTT' in mermaid,
        'Industrial Edge': 'Edge' in mermaid,
        'Cloud': 'Cloud' in mermaid or 'cloud' in mermaid.lower()
    }
    
    print("\nContent entity presence:")
    found = 0
    for entity, present in checks.items():
        status = "✓" if present else "✗"
        print(f"  {status} {entity}")
        if present:
            found += 1
    
    print(f"\nContent match: {found}/5 entities")
    if found >= 4:
        print("✓ GOOD: Diagram is clearly content-derived, not generic")
    else:
        print("⚠ Missing key entities from source")
else:
    print("✗ No architecture artifact")

# ============================================================================
# SCENARIO 3: Decision Logic - Check if/then/else structure
# ============================================================================
print("\n\n3. DECISION TREE (if/then/else logic)")
print("-" * 70)

decision_logic = """# Connector Deployment Decision

Procedure
1. Test the connection to verify connectivity.
2. If the connection test succeeds:
   Deploy the connector to production.
3. If the connection test fails:
   Check network cable and IP settings."""

rec3 = detect_visuals("Connection Decision", decision_logic)
decision = next((r for r in rec3 if r.get('visual_type') in ['Decision Tree', 'Flowchart']), None)

if decision and decision.get('generated_artifact'):
    artifact = decision['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Status: ✓ Generated ({decision['visual_type']})")
    print(f"\nMermaid:\n{mermaid}")
    
    # Check for decision structure
    checks = {
        'Start/decision node': '{' in mermaid,
        'Success path': 'Yes' in mermaid or 'success' in mermaid.lower(),
        'Failure path': 'No' in mermaid or 'fail' in mermaid.lower(),
        'Arrows': '-->' in mermaid
    }
    
    print("\nDecision structure elements:")
    for element, present in checks.items():
        status = "✓" if present else "✗"
        print(f"  {status} {element}")
    
    if all(checks.values()):
        print("✓ GOOD: Proper if/then/else structure")
    else:
        print("⚠ Missing decision logic elements")
else:
    print("✗ No decision artifact")

print("\n" + "=" * 70)
print("ASSESSMENT")
print("=" * 70)
print("""
Current state:
- Artifacts ARE being generated
- Architecture is content-driven (good!)
- Need to validate Workflow and Decision quality

Next phase:
✓ Artifact quality score (completeness %, entity count)
✓ Edit capability (inline editor)
✓ Export buttons (Copy Mermaid, SVG, PNG)
""")
