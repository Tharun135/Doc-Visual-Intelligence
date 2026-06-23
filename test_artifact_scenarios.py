#!/usr/bin/env python3
"""Test artifact generation against three critical scenarios"""

from analyzers.visual_detector import detect_visuals

print("=" * 70)
print("ARTIFACT GENERATION - CRITICAL SCENARIO TESTING")
print("=" * 70)

# ============================================================================
# SCENARIO 1: Long Procedures (20 steps)
# ============================================================================
print("\n1. LONG PROCEDURE TEST (20 steps)")
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
workflow1 = next((r for r in rec1 if r.get('visual_type') == 'Workflow Diagram'), None)

if workflow1 and workflow1.get('generated_artifact'):
    artifact = workflow1['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Visual Type: {workflow1['visual_type']}")
    print(f"Generated Mermaid lines: {len(mermaid.split(chr(10)))}")
    print(f"\nFirst 500 chars of Mermaid:")
    print(mermaid[:500])
    
    # Check if grouped or flat
    if 'subgraph' in mermaid.lower() or 'group' in mermaid.lower():
        print("✓ GOOD: Uses subgraphs/grouping for readability")
    elif mermaid.count('-->') > 15:
        print("⚠ WARNING: Flat linear chain detected (may be hard to read)")
        print("   Suggest: Implement subgraph grouping for long procedures")
    else:
        print("✓ GOOD: Linear chain but manageable length")
else:
    print("✗ No workflow artifact generated for long procedure")

# ============================================================================
# SCENARIO 2: Real Architecture (content-driven, not generic)
# ============================================================================
print("\n\n2. REAL ARCHITECTURE TEST (content-driven entities)")
print("-" * 70)

real_architecture = """# Industrial Data Pipeline

System Architecture
The PLC publishes sensor data to the EtherNet/IP Connector.
The EtherNet/IP Connector publishes to the MQTT Broker.
The MQTT Broker forwards time-series data to Industrial Edge.
Industrial Edge stores data and communicates with the cloud database.
The cloud database provides analytics and reporting interfaces."""

rec2 = detect_visuals("Data Pipeline Architecture", real_architecture)
arch2 = next((r for r in rec2 if r.get('visual_type') in ['Architecture Diagram', 'Topology Diagram']), None)

if arch2 and arch2.get('generated_artifact'):
    artifact = arch2['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Visual Type: {arch2['visual_type']}")
    print(f"Generated Mermaid:\n{mermaid}")
    
    # Check for content-specific entities
    expected_entities = ['PLC', 'EtherNet', 'MQTT', 'Cloud']
    found = []
    for entity in expected_entities:
        if entity.lower() in mermaid.lower():
            found.append(entity)
    
    print(f"\nContent-specific entities found: {found}")
    if len(found) >= 3:
        print("✓ GOOD: Diagram is content-derived, not generic template")
    else:
        print(f"⚠ WARNING: Expected entities not found. Got {len(found)}/4")
        print(f"   (Mermaid does have: {[e for e in ['Gateway', 'Server', 'Cloud'] if e.lower() in mermaid.lower()]})")
else:
    print("✗ No architecture artifact generated")

# ============================================================================
# SCENARIO 3: Decision Logic (if/then/else structure)
# ============================================================================
print("\n\n3. DECISION LOGIC TEST (if/then/else conditions)")
print("-" * 70)

decision_logic = """# Connector Deployment Decision Flow

Procedure
1. Test the connection to verify connectivity.
2. If the connection test succeeds:
   a. Validate PLC response time.
   b. Deploy the connector to production.
   c. Enable real-time data logging.
3. If the connection test fails:
   a. Check network cable and IP settings.
   b. Review firewall rules.
   c. Verify PLC is powered on and accessible.
4. If after review the connection still fails:
   a. Contact network administrator.
   b. Escalate to support team."""

rec3 = detect_visuals("Connection Decision Logic", decision_logic)
decision3 = next((r for r in rec3 if r.get('visual_type') in ['Decision Tree', 'Flowchart']), None)

if decision3 and decision3.get('generated_artifact'):
    artifact = decision3['generated_artifact']
    mermaid = artifact.get('mermaid', '')
    print(f"Visual Type: {decision3['visual_type']}")
    print(f"Generated Mermaid:\n{mermaid}")
    
    # Check for decision nodes
    if '{' in mermaid and '}' in mermaid:
        print("\n✓ GOOD: Contains decision nodes (if/then/else)")
    else:
        print("\n⚠ WARNING: No decision nodes detected")
        print("   Check if conditional logic was properly extracted")
else:
    print("✗ No decision artifact generated for conditional content")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("SCENARIO TEST COMPLETE")
print("=" * 70)
print("""
Next steps based on results:
1. If Scenario 1 shows flat chain: implement subgraph grouping
2. If Scenario 2 shows generic entities: verify entity extraction is content-driven
3. If Scenario 3 shows no decision nodes: improve conditional parsing

Then add:
- Artifact quality score (completeness %, confidence, entity count)
- Edit capability (inline Mermaid editor)
- Direct export (Copy, Download SVG/PNG)
""")
