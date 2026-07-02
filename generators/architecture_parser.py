"""Architecture diagram parser - extract components and relationships from documentation."""

import json
import re
from pathlib import Path
from typing import Optional


RELATIONSHIP_VERBS = {
    "connects to": "connects",
    "connects": "connects",
    "connect": "connects",
    "connected to": "connects",
    "communicates with": "communicates",
    "communicates": "communicates",
    "communicate with": "communicates",
    "sends": "sends",
    "send": "sends",
    "publishes": "publishes",
    "publish": "publishes",
    "subscribes": "subscribes",
    "subscribe": "subscribes",
    "receives": "receives",
    "receive": "receives",
    "forwards": "forwards",
    "forward": "forwards",
    "routes": "routes",
    "route": "routes",
    "writes": "writes",
    "write": "writes",
    "reads": "reads",
    "read": "reads",
    "uploads": "uploads",
    "upload": "uploads",
    "downloads": "downloads",
    "download": "downloads",
    "imports": "imports",
    "import": "imports",
    "exports": "exports",
    "export": "exports",
    "aggregates": "aggregates",
    "aggregate": "aggregates",
    "stores": "stores",
    "store": "stores",
    "processes": "processes",
    "process": "processes",
    "runs on": "runs_on",
    "run on": "runs_on",
    "installed on": "installed_on",
    "install on": "installed_on",
    "hosted on": "hosted_on",
    "host on": "hosted_on",
    "deployed on": "deployed_on",
    "deploy on": "deployed_on",
    "acts as client on": "client_on",
    "acts as a client on": "client_on",
}

PROTOCOL_PATTERNS = [
    "OPC UA",
    "OPC-UA",
    "MQTT",
    "REST",
    "HTTPS",
    "HTTP",
    "PROFINET",
    "Ethernet",
    "TCP/IP",
    "UDP",
    "WebSocket",
    "gRPC",
    "GraphQL",
    "SOAP",
    "JSON-RPC",
    "Serial",
    "Modbus",
    "DNP3",
    "IEC 60870-5-104",
    "AMQP",
]

KNOWN_ENTITIES = {
    "cloud": {
        "aliases": ["cloud", "cloud platform", "cloud service", "aws", "azure", "gcp", "cloud server"],
        "type": "cloud",
    },
    "gateway": {
        "aliases": ["gateway", "access point", "network bridge", "iot gateway", "edge gateway", "reverse proxy"],
        "type": "gateway",
    },
    "server": {
        "aliases": ["server", "backend", "application server", "web server", "database server", "service", "host"],
        "type": "server",
    },
    "database": {
        "aliases": ["database", "db", "repository", "datastore", "sql", "nosql", "cache"],
        "type": "database",
    },
    "plc": {
        "aliases": ["plc", "controller", "cpu", "processor", "s7-1500", "s7-1200", "s7-300", "microcontroller"],
        "type": "device",
    },
    "edge": {
        "aliases": ["edge device", "edge", "edge node", "edge application", "unified on edge", "iot device"],
        "type": "runtime",
    },
    "connector": {
        "aliases": ["connector", "adapter", "bridge", "driver", "interface", "middleware", "agent"],
        "type": "application",
    },
    "ui": {
        "aliases": ["hmi", "panel", "dashboard", "ui", "screen", "interface", "display", "console", "visualization"],
        "type": "interface",
    },
    "iih": {
        "aliases": ["iih", "iih semantics", "semantics server", "iih cloud", "siemens cloud"],
        "type": "cloud",
    },
}

TYPE_NORMALIZATION = {
    "network_component": "gateway",
    "system": "server",
}

GENERIC_PREFIX_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
ENTITY_TRAILING_RELATIONSHIP_RE = re.compile(
    r"\b(?:"
    r"connects?|connected|communicates?|send(?:s)?|publish(?:es)?|subscribe(?:s)?|"
    r"receive(?:s)?|forward(?:s)?|route(?:s)?|write(?:s)?|read(?:s)?|"
    r"upload(?:s)?|download(?:s)?|import(?:s)?|export(?:s)?|"
    r"aggregate(?:s)?|store(?:s)?|process(?:es)?|transform(?:s)?"
    r")\b.*$",
    re.IGNORECASE,
)

GENERIC_NODE_NAMES = {
    "application",
    "server",
    "gateway",
    "database",
    "cloud",
    "connector",
    "edge",
    "edge device",
    "device",
    "controller",
    "runtime",
    "ui",
    "ui component",
}


def _load_knowledge_model() -> dict:
    """Load knowledge model with entity definitions."""
    defaults = {"entities": KNOWN_ENTITIES, "relationships": []}
    try:
        path = Path(__file__).parent.parent / "rules" / "knowledge_model.json"
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict) and "entities" in loaded:
            defaults["entities"].update(loaded.get("entities", {}))
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def _canonicalize_entity(text: str, knowledge: dict) -> Optional[str]:
    text_lower = text.lower().strip()
    if not text_lower:
        return None

    text_normalized = re.sub(r"['s]+$", "", text_lower)

    for canonical, entity_def in knowledge.get("entities", {}).items():
        aliases = entity_def.get("aliases", [])
        if text_lower in aliases or canonical.lower() == text_lower:
            return canonical
        if text_normalized in aliases or re.sub(r"['s]+$", "", canonical.lower()) == text_normalized:
            return canonical

    for canonical in knowledge.get("entities", {}):
        if canonical.lower() in text_lower:
            return canonical

    return None


def _normalize_type(entity_type: str) -> str:
    normalized = (entity_type or "application").strip().lower()
    return TYPE_NORMALIZATION.get(normalized, normalized)


def _slugify(text: str) -> str:
    normalized = GENERIC_PREFIX_RE.sub("", text.strip())
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_")
    return normalized.lower() or "component"


def _clean_entity_phrase(text: str) -> str:
    cleaned = GENERIC_PREFIX_RE.sub("", text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\b(using|via|over|through|for)\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = ENTITY_TRAILING_RELATIONSHIP_RE.sub("", cleaned)
    cleaned = re.sub(r"\bacts?\s+as\s+(?:an?\s+)?client\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:it|they|this|that)\b\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(and|or)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.;:")


def _extract_protocol(text: str) -> Optional[str]:
    for protocol in PROTOCOL_PATTERNS:
        if protocol.lower() in text.lower():
            return protocol
    return None


def _infer_node_type(entity_text: str, knowledge: dict) -> str:
    canonical = _canonicalize_entity(entity_text, knowledge)
    if canonical:
        entity_def = knowledge.get("entities", {}).get(canonical, {})
        return _normalize_type(entity_def.get("type", "application"))

    text_lower = entity_text.lower()
    for entity_def in knowledge.get("entities", {}).values():
        for alias in entity_def.get("aliases", []):
            if re.search(r"\b" + re.escape(alias.lower()) + r"\b", text_lower):
                return _normalize_type(entity_def.get("type", "application"))

    heuristic_types = {
        "cloud": "cloud",
        "gateway": "gateway",
        "server": "server",
        "database": "database",
        "db": "database",
        "plc": "device",
        "device": "device",
        "controller": "device",
        "application": "application",
        "runtime": "runtime",
        "connector": "application",
        "adapter": "application",
        "hmi": "interface",
        "ui": "interface",
        "dashboard": "interface",
    }
    for keyword, inferred_type in heuristic_types.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
            return inferred_type

    return "application"


def _extract_component_mentions(text: str, knowledge: dict) -> list[dict]:
    """Extract likely component names from title-case architecture phrases."""
    mentions: dict[str, dict] = {}

    title_case_pattern = (
        r"\b([A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*)*"
        r"\s+(?:Application|Server|Gateway|Device|Connector|Runtime|Database|PLC|Controller|System))\b"
    )
    for match in re.finditer(title_case_pattern, text):
        phrase = _clean_entity_phrase(match.group(1))
        if not phrase:
            continue
        node_id = _slugify(phrase)
        mentions[node_id] = {
            "id": node_id,
            "name": phrase,
            "type": _infer_node_type(phrase, knowledge),
        }

    return list(mentions.values())


def _collapse_generic_nodes(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map generic node mentions to specific node mentions when unambiguous."""
    node_by_id = {node["id"]: node for node in nodes}
    remap: dict[str, str] = {}

    for node in nodes:
        node_name_lower = node["name"].strip().lower()
        if node_name_lower not in GENERIC_NODE_NAMES:
            continue

        candidates = [
            candidate for candidate in nodes
            if candidate["id"] != node["id"]
            and node_name_lower in candidate["name"].lower()
        ]
        if len(candidates) == 1:
            remap[node["id"]] = candidates[0]["id"]

    if not remap:
        return nodes, edges

    updated_edges = []
    seen = set()
    for edge in edges:
        source = remap.get(edge["source"], edge["source"])
        target = remap.get(edge["target"], edge["target"])
        key = (source, target, edge.get("type"), edge.get("protocol") or "")
        if key in seen or source == target:
            continue
        seen.add(key)
        updated_edges.append(
            {
                "source": source,
                "target": target,
                "type": edge.get("type"),
                "protocol": edge.get("protocol"),
                "label": edge.get("label"),
            }
        )

    filtered_nodes = [node for node in nodes if node["id"] not in remap]
    filtered_nodes = [node for node in filtered_nodes if node["id"] in {e["source"] for e in updated_edges} | {e["target"] for e in updated_edges}]
    return filtered_nodes, updated_edges


def _find_relationships_in_text(text: str) -> list[dict]:
    """Extract (source, target, type, protocol) from architecture prose."""
    relationships = []
    knowledge = _load_knowledge_model()

    sentence_candidates = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s and s.strip()
    ]

    forward_verbs = r"(?:sends?|publishes?|forwards?|routes?|writes?|exports?|uploads?|process(?:es)?|stores?|aggregates?)"
    reverse_verbs = r"(?:receives?|reads?|imports?|downloads?|subscribes?)"
    peer_verbs = r"(?:connects?\s+to|connects?|connected\s+to|communicates?\s+with|communicate\s+with)"
    containment_verbs = r"(?:runs?\s+on|installed\s+on|hosted\s+on|deployed\s+on|acts?\s+as\s+(?:an?\s+)?client\s+on)"

    patterns = [
        (
            rf"^(?P<src>.+?)\s+(?P<verb>{containment_verbs})\s+(?P<dst>.+?)(?:\s+(?:using|via|over|through|with)\s+(?P<proto>[^.;,]+))?$",
            "containment",
        ),
        (
            rf"^(?P<src>.+?)\s+(?P<verb>{forward_verbs})\s+(?:.+?\s+)?to\s+(?P<dst>.+?)(?:\s+(?:using|via|over|through|with)\s+(?P<proto>[^.;,]+))?$",
            "forward",
        ),
        (
            rf"^(?P<dst>.+?)\s+(?P<verb>{reverse_verbs})\s+(?:.+?\s+)?from\s+(?P<src>.+?)(?:\s+(?:using|via|over|through|with)\s+(?P<proto>[^.;,]+))?$",
            "reverse",
        ),
        (
            rf"^(?P<src>.+?)\s+(?P<verb>{peer_verbs})\s+(?P<dst>.+?)(?:\s+(?:using|via|over|through|with)\s+(?P<proto>[^.;,]+))?$",
            "peer",
        ),
    ]

    for sentence in sentence_candidates:
        sentence_clean = sentence.strip().strip(".;")
        for pattern, direction in patterns:
            match = re.match(pattern, sentence_clean, re.IGNORECASE)
            if not match:
                continue

            source_raw = _clean_entity_phrase(match.group("src"))
            target_raw = _clean_entity_phrase(match.group("dst"))
            if not source_raw or not target_raw:
                continue
            if source_raw.lower() == target_raw.lower():
                continue

            verb_text = re.sub(r"\s+", " ", match.group("verb").strip().lower())
            verb_type = RELATIONSHIP_VERBS.get(verb_text, verb_text)
            protocol_raw = (match.group("proto") or "").strip()
            protocol = _extract_protocol(protocol_raw) or _extract_protocol(sentence_clean)

            relationships.append(
                {
                    "source": source_raw,
                    "target": target_raw,
                    "source_id": _slugify(source_raw),
                    "target_id": _slugify(target_raw),
                    "source_type": _infer_node_type(source_raw, knowledge),
                    "target_type": _infer_node_type(target_raw, knowledge),
                    "type": verb_type,
                    "protocol": protocol,
                    "source_raw": source_raw,
                    "target_raw": target_raw,
                    "direction": direction,
                    "semantic": "containment" if direction == "containment" else "connection",
                }
            )
            break

    return relationships


def parse_section_for_architecture(section_title: str, section_content: str, force_parse: bool = False) -> Optional[dict]:
    """Parse one section into an architecture graph model."""
    title_lower = section_title.lower()
    architecture_keywords = [
        "architecture",
        "system design",
        "infrastructure",
        "components",
        "topology",
        "deployment",
        "system",
        "pipeline",
    ]
    is_architecture_section = force_parse or any(kw in title_lower for kw in architecture_keywords)

    if not is_architecture_section:
        knowledge = _load_knowledge_model()
        entity_mentions = 0
        for entity_def in knowledge.get("entities", {}).values():
            for alias in entity_def.get("aliases", []):
                entity_mentions += len(re.findall(r"\b" + re.escape(alias) + r"\b", section_content, re.IGNORECASE))

        relationships = _find_relationships_in_text(section_content)
        is_architecture_section = entity_mentions >= 3 and len(relationships) >= 2

    if not is_architecture_section:
        return None

    knowledge = _load_knowledge_model()
    relationships = _find_relationships_in_text(section_content)

    extracted_components = _extract_component_mentions(section_content, knowledge)
    node_index = {node["id"]: node for node in extracted_components}

    for rel in relationships:
        if rel["source_id"] not in node_index:
            node_index[rel["source_id"]] = {
                "id": rel["source_id"],
                "name": rel["source"],
                "type": rel["source_type"],
            }
        if rel["target_id"] not in node_index:
            node_index[rel["target_id"]] = {
                "id": rel["target_id"],
                "name": rel["target"],
                "type": rel["target_type"],
            }

    if not node_index or not relationships:
        return None

    nodes = sorted(node_index.values(), key=lambda node: node["name"].lower())

    edges = []
    seen_edges = set()
    for rel in relationships:
        edge_key = (rel["source_id"], rel["target_id"], rel["type"], rel.get("protocol") or "")
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(
            {
                "source": rel["source_id"],
                "target": rel["target_id"],
                "type": rel["type"],
                "protocol": rel["protocol"],
                "label": rel["protocol"] if rel["protocol"] else rel["type"],
                "semantic": rel.get("semantic", "connection"),
            }
        )

    nodes, edges = _collapse_generic_nodes(nodes, edges)

    return {
        "title": section_title,
        "nodes": nodes,
        "edges": edges,
        "entities_found": len(nodes),
        "relationships_found": len(relationships),
    }


def extract_architecture_models(sections: list[dict]) -> list[dict]:
    """Extract architecture models from all sections."""
    models = []
    for section in sections:
        title = section.get("title", "")
        content = section.get("content", "")
        model = parse_section_for_architecture(title, content)
        if model:
            models.append(model)
    return models
