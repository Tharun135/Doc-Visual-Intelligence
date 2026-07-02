from generators.architecture_parser import parse_section_for_architecture, _find_relationships_in_text, _load_knowledge_model
import re

test_content = '''
The Edge Device receives data from sensors and sends it to the Connector.

The Connector transforms data and uploads it to the Server.

The Server processes data and writes results to a Database.

The Database exports reports to an external Cloud service using HTTPS.

The UI Dashboard displays data from the Server in real-time.
'''

# Manually run through the detection logic
title_lower = "data processing pipeline"
architecture_keywords = ["architecture", "system design", "infrastructure", "components", "topology", "deployment", "system", "pipeline"]
is_architecture_section = any(kw in title_lower for kw in architecture_keywords)

print(f"Title detected: {is_architecture_section}")

if is_architecture_section:
    print("-> Title matches architecture keywords, should proceed")
else:
    print("-> Title doesn't match, checking density")
    knowledge = _load_knowledge_model()
    entity_mentions = 0
    for canonical, entity_def in knowledge.get("entities", {}).items():
        aliases = entity_def.get("aliases", [])
        for alias in aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            matches = len(re.findall(pattern, test_content, re.IGNORECASE))
            entity_mentions += matches

    from generators.architecture_parser import RELATIONSHIP_VERBS
    relationship_verbs_found = 0
    for verb_phrase in RELATIONSHIP_VERBS.keys():
        matches = len(re.findall(re.escape(verb_phrase), test_content, re.IGNORECASE))
        relationship_verbs_found += matches
        
    print(f"  Entities: {entity_mentions}, Relationships: {relationship_verbs_found}")
    density_check = entity_mentions >= 3 and relationship_verbs_found >= 3
    print(f"  Density check: {density_check}")

# Actually call the function
model = parse_section_for_architecture("Data Processing Pipeline", test_content)
print(f"\nResult: {model is not None}")
if model:
    print(f"Nodes: {[n['name'] for n in model['nodes']]}")
