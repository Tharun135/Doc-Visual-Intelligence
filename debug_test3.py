from generators.architecture_parser import parse_section_for_architecture, _load_knowledge_model, RELATIONSHIP_VERBS
import re

test_content = '''
The Edge Device receives data from sensors and sends it to the Connector.

The Connector transforms data and uploads it to the Server.

The Server processes data and writes results to a Database.

The Database exports reports to an external Cloud service using HTTPS.

The UI Dashboard displays data from the Server in real-time.
'''

# Check entity count
knowledge = _load_knowledge_model()
entity_mentions = 0
for canonical, entity_def in knowledge.get('entities', {}).items():
    aliases = entity_def.get('aliases', [])
    for alias in aliases:
        pattern = r'\b' + re.escape(alias) + r'\b'
        matches = len(re.findall(pattern, test_content, re.IGNORECASE))
        entity_mentions += matches

# Check relationship count
relationship_verbs_found = 0
for verb_phrase in RELATIONSHIP_VERBS.keys():
    matches = len(re.findall(re.escape(verb_phrase), test_content, re.IGNORECASE))
    relationship_verbs_found += matches

print(f"Entities: {entity_mentions} (threshold: 3)")
print(f"Relationships: {relationship_verbs_found} (threshold: 3)")
print(f"Title 'Data Processing Pipeline' contains 'pipeline': {'pipeline' in 'data processing pipeline'}")
print(f"Would detect: {entity_mentions >= 3 and relationship_verbs_found >= 3}")

model = parse_section_for_architecture("Data Processing Pipeline", test_content)
print(f"Actually detected: {model is not None}")
