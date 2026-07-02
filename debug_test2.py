from generators.architecture_parser import parse_section_for_architecture

test_content = '''
The system consists of edge devices running connectors. Connectors publish metrics to the MQTT Gateway.

The Gateway aggregates data and sends it to the Cloud Platform via HTTPS.

The Cloud Platform stores data in a Database and exposes it through a REST API.

The HMI Dashboard subscribes to Gateway updates using WebSocket connections.

PLCs at the field level communicate with edge devices using Modbus.
'''

model = parse_section_for_architecture("IoT Deployment Architecture", test_content)
if model:
    print("Nodes:", [n['name'] for n in model['nodes']])
    print("Edges:")
    for edge in model['edges']:
        print(f"  {edge['source']} -> {edge['target']} ({edge.get('label', '—')})")
else:
    print("Not detected as architecture")
