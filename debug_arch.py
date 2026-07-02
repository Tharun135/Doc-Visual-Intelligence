from generators.architecture_parser import _find_relationships_in_text

test_content = '''
The system consists of edge devices running connectors. Connectors publish metrics to the MQTT Gateway.

The Gateway aggregates data and sends it to the Cloud Platform via HTTPS.

The Cloud Platform stores data in a Database and exposes it through a REST API.

The HMI Dashboard subscribes to Gateway updates using WebSocket connections.

PLCs at the field level communicate with edge devices using Modbus.
'''

rels = _find_relationships_in_text(test_content)
print(f'Relationships found: {len(rels)}')
for rel in rels:
    print(f'  {rel["source"]} -> {rel["target"]} ({rel.get("protocol", "None")})')
