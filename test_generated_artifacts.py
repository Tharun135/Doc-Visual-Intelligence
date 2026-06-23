from analyzers.visual_detector import detect_visuals

samples = [
    (
        "Procedure",
        "# Configure EtherNet/IP Connector\n\n1. Open Connectors.\n2. Select Add Connector.\n3. Select EtherNet/IP Connector.\n4. Enter name and description.\n5. Configure PLC connection.\n6. Define tags.\n7. Deploy connector.\n8. Verify connection status."
    ),
    (
        "Architecture",
        "The PLC sends data to EtherNet/IP Connector. The connector publishes data to Industrial Edge. Industrial Edge communicates with Cloud."
    ),
    (
        "Decision",
        "If connection succeeds, deploy the connector. Otherwise, review network settings."
    ),
    (
        "Troubleshooting",
        "Error 101:\nCheck network cable.\n\nError 102:\nVerify PLC IP address.\n\nError 103:\nRestart connector."
    )
]

for title, content in samples:
    print("=" * 30)
    print(title)
    results = detect_visuals(title, content)
    for item in results:
        artifact = item.get("generated_artifact")
        if not artifact:
            continue
        print(item["visual_type"])
        print(artifact["artifact_type"])
        print(artifact["mermaid"])
        print("PLANTUML")
        print(artifact["plantuml"])
        break
