from generators.architecture_parser import _find_relationships_in_text, _load_knowledge_model
import re

test_content = '''
The Edge Device receives data from sensors and sends it to the Connector.

The Connector transforms data and uploads it to the Server.

The Server processes data and writes results to a Database.

The Database exports reports to an external Cloud service using HTTPS.

The UI Dashboard displays data from the Server in real-time.
'''

rels = _find_relationships_in_text(test_content)
print(f"Relationships extracted: {len(rels)}")
for rel in rels:
    print(f"  {rel['source']} -> {rel['target']}")

# Check entities
knowledge = _load_knowledge_model()
entities = set()
for canonical, entity_def in knowledge.get('entities', {}).items():
    aliases = entity_def.get('aliases', [])
    for alias in aliases:
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, test_content, re.IGNORECASE):
            entities.add(canonical)
        elif re.search(pattern + 's', test_content, re.IGNORECASE):
            entities.add(canonical)
        elif re.search(pattern + "'s", test_content, re.IGNORECASE):
            entities.add(canonical)

print(f"Entities from scanning: {entities}")

for rel in rels:
    entities.add(rel['source'])
    entities.add(rel['target'])

print(f"Entities after adding from relationships: {entities}")
print(f"Would proceed: {bool(entities) and bool(rels)}")
