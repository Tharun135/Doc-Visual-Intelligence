from generators.architecture_parser import _load_knowledge_model

knowledge = _load_knowledge_model()
print("Known entities:")
for name, defn in knowledge.get('entities', {}).items():
    print(f'  {name}: {defn.get("type", "?")} - aliases: {defn.get("aliases", [])[:2]}')
