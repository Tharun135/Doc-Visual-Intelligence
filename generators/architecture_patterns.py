"""
Detect architectural patterns and recommend layout strategies.

Patterns recognized:
- CLIENT_SERVER: Clear source/sink, directional flow
- EDGE_COMPUTING: Edge devices feeding into cloud/backend
- GATEWAY_HUB: Central gateway with periphery
- PUB_SUB: Publishers → broker/topic → subscribers
- LAYERED: Clear tier hierarchy (UI → logic → DB)
- PEER_MESH: Bidirectional/mesh communications
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ArchPattern(Enum):
    CLIENT_SERVER = "client_server"
    EDGE_COMPUTING = "edge_computing"
    GATEWAY_HUB = "gateway_hub"
    PUB_SUB = "pub_sub"
    LAYERED = "layered"
    PEER_MESH = "peer_mesh"
    GENERIC = "generic"


@dataclass
class PatternAnalysis:
    pattern: ArchPattern
    confidence: float  # 0-1: how strongly does this match?
    hub_node: Optional[str] = None  # For hub patterns
    layers: Optional[list[list[str]]] = None  # For layered patterns
    evidence: list[str] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


def _count_in_degree(node_id: str, edges: list[dict]) -> int:
    """Count edges where node is target."""
    return sum(1 for e in edges if e["target"] == node_id)


def _count_out_degree(node_id: str, edges: list[dict]) -> int:
    """Count edges where node is source."""
    return sum(1 for e in edges if e["source"] == node_id)


def _is_likely_client(node_name: str) -> bool:
    """Heuristic: is this node likely a client/consumer?"""
    terms = {"ui", "dashboard", "hmi", "panel", "application", "app", "client", "edge device", "edge"}
    return any(term in node_name.lower() for term in terms)


def _is_likely_server(node_name: str) -> bool:
    """Heuristic: is this node likely a server/provider?"""
    terms = {"server", "cloud", "backend", "database", "db", "service", "broker", "hub", "platform", "iih"}
    return any(term in node_name.lower() for term in terms)


def _is_likely_gateway(node_name: str) -> bool:
    """Heuristic: is this node likely a gateway/hub?"""
    terms = {"gateway", "broker", "hub", "router", "proxy", "aggregator"}
    return any(term in node_name.lower() for term in terms)


def _is_likely_edge(node_name: str) -> bool:
    """Heuristic: is this node at the edge?"""
    terms = {"edge", "device", "plc", "sensor", "actuator", "iot"}
    return any(term in node_name.lower() for term in terms)


def _is_likely_cloud(node_name: str) -> bool:
    """Heuristic: is this node cloud-hosted?"""
    terms = {"cloud", "aws", "azure", "gcp", "backend", "server"}
    return any(term in node_name.lower() for term in terms)


def _detect_client_server(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect clear client → server pattern.
    Characteristics: one node with high out-degree (client), one with high in-degree (server).
    Fallback pattern for generic request-response.
    """
    if len(nodes) < 2 or len(edges) < 1:
        return None

    # Skip if this looks like edge computing or pub-sub
    edge_nodes = [n for n in nodes if _is_likely_edge(n["name"])]
    if edge_nodes and any(_is_likely_cloud(n["name"]) for n in nodes):
        # Likely edge computing, not client-server
        return None

    in_degrees = {n["id"]: _count_in_degree(n["id"], edges) for n in nodes}
    out_degrees = {n["id"]: _count_out_degree(n["id"], edges) for n in nodes}

    # Find potential client (high out, low in) and server (high in, low out)
    clients = [n for n in nodes if out_degrees[n["id"]] > in_degrees[n["id"]] and out_degrees[n["id"]] >= 1]
    servers = [n for n in nodes if in_degrees[n["id"]] > out_degrees[n["id"]] and in_degrees[n["id"]] >= 1]

    if clients and servers:
        # Further heuristic check
        client_names_match = sum(1 for c in clients if _is_likely_client(c["name"]))
        server_names_match = sum(1 for s in servers if _is_likely_server(s["name"]))

        if client_names_match > 0 or server_names_match > 0:
            confidence = 0.6 + (0.2 if client_names_match > 0 else 0) + (0.2 if server_names_match > 0 else 0)
            return PatternAnalysis(
                pattern=ArchPattern.CLIENT_SERVER,
                confidence=min(confidence, 1.0),
                evidence=[
                    f"{len(clients)} client node(s): {', '.join(c['name'] for c in clients[:2])}",
                    f"{len(servers)} server node(s): {', '.join(s['name'] for s in servers[:2])}",
                ],
            )

    return None


def _detect_edge_computing(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect edge → cloud/backend pattern.
    Characteristics: edge/device nodes feeding into cloud/server nodes.
    Priority detection for IoT architectures.
    """
    if len(nodes) < 2:
        return None

    edge_nodes = [n for n in nodes if _is_likely_edge(n["name"])]
    cloud_nodes = [n for n in nodes if _is_likely_cloud(n["name"])]

    if not edge_nodes or not cloud_nodes:
        return None

    # Check if ANY edge points from edge to cloud
    edge_to_cloud_edges = [
        e for e in edges if any(e["source"] == en["id"] for en in edge_nodes)
        and any(e["target"] == cn["id"] for cn in cloud_nodes)
    ]

    if not edge_to_cloud_edges:
        return None

    # This is a strong edge computing signal
    # Boost confidence if we have multiple edge nodes
    base_confidence = 0.75
    if len(edge_nodes) > 1:
        base_confidence = 0.85
    if len(edge_to_cloud_edges) > 1:
        base_confidence = 0.90

    return PatternAnalysis(
        pattern=ArchPattern.EDGE_COMPUTING,
        confidence=min(base_confidence, 1.0),
        evidence=[
            f"{len(edge_nodes)} edge device(s): {', '.join(n['name'] for n in edge_nodes[:3])}",
            f"{len(cloud_nodes)} cloud/backend node(s): {', '.join(n['name'] for n in cloud_nodes[:3])}",
            f"{len(edge_to_cloud_edges)} edge→cloud relationship(s)",
        ],
    )


def _detect_gateway_hub(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect hub-and-spoke/gateway pattern.
    Characteristics: one central node connected to many others.
    """
    if len(nodes) < 3:
        return None

    in_degrees = {n["id"]: _count_in_degree(n["id"], edges) for n in nodes}
    out_degrees = {n["id"]: _count_out_degree(n["id"], edges) for n in nodes}
    total_degrees = {n["id"]: in_degrees[n["id"]] + out_degrees[n["id"]] for n in nodes}

    # Find node with highest degree
    hub_candidates = sorted(nodes, key=lambda n: total_degrees[n["id"]], reverse=True)

    if hub_candidates:
        hub = hub_candidates[0]
        hub_degree = total_degrees[hub["id"]]
        other_nodes_avg_degree = sum(total_degrees[n["id"]] for n in nodes[1:]) / max(1, len(nodes) - 1)

        # Hub should have significantly higher degree
        if hub_degree > other_nodes_avg_degree * 1.5:
            # Further check: is this node a gateway?
            is_gateway = _is_likely_gateway(hub["name"])
            confidence = 0.65 + (0.25 if is_gateway else 0.1)

            return PatternAnalysis(
                pattern=ArchPattern.GATEWAY_HUB,
                confidence=min(confidence, 1.0),
                hub_node=hub["id"],
                evidence=[
                    f"Central hub: {hub['name']}",
                    f"Hub degree: {hub_degree}, avg others: {other_nodes_avg_degree:.1f}",
                    f"Connected to {len(nodes) - 1} other node(s)",
                ],
            )

    return None


def _detect_pub_sub(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect pub-sub pattern.
    Characteristics: multiple publishers and subscribers converging on a broker/topic.
    """
    if len(nodes) < 3:
        return None

    # Look for "publish" or "subscribe" verbs in edge labels/types
    pub_keywords = {"publish", "publishes", "published"}
    sub_keywords = {"subscribe", "subscribes", "subscribed"}

    pub_edges = [e for e in edges if any(k in str(e.get("type", "")).lower() for k in pub_keywords)]
    sub_edges = [e for e in edges if any(k in str(e.get("type", "")).lower() for k in sub_keywords)]

    if pub_edges and sub_edges:
        # Check if there's a common intermediary
        pub_targets = set(e["target"] for e in pub_edges)
        sub_sources = set(e["source"] for e in sub_edges)
        common = pub_targets & sub_sources

        if common:
            broker_id = list(common)[0]
            broker = next((n for n in nodes if n["id"] == broker_id), None)
            if broker:
                return PatternAnalysis(
                    pattern=ArchPattern.PUB_SUB,
                    confidence=0.8,
                    hub_node=broker_id,
                    evidence=[
                        f"Broker/Topic: {broker['name']}",
                        f"{len(pub_edges)} publisher(s)",
                        f"{len(sub_edges)} subscriber(s)",
                    ],
                )

    return None


def _detect_layered(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect layered/tiered pattern.
    Characteristics: clear vertical dependency chain with minimal cross-layer connections.
    """
    if len(nodes) < 3:
        return None

    # Use simple heuristics: UI → Logic → Data
    ui_nodes = [n for n in nodes if any(t in n["name"].lower() for t in ["ui", "dashboard", "hmi", "panel"])]
    logic_nodes = [n for n in nodes if any(t in n["name"].lower() for t in ["application", "server", "service", "connector"])]
    data_nodes = [n for n in nodes if any(t in n["name"].lower() for t in ["database", "db", "cache"])]

    layers = []
    if ui_nodes:
        layers.append(ui_nodes)
    if logic_nodes:
        layers.append(logic_nodes)
    if data_nodes:
        layers.append(data_nodes)

    if len(layers) >= 2:
        # Check connectivity matches layering
        cross_layer_count = 0
        for i, layer in enumerate(layers[:-1]):
            for node in layer:
                for target in [e["target"] for e in edges if e["source"] == node["id"]]:
                    if not any(target == n["id"] for n in layers[i + 1]):
                        cross_layer_count += 1

        cross_layer_ratio = cross_layer_count / max(1, len(edges))
        if cross_layer_ratio < 0.3:  # Most edges follow layer hierarchy
            return PatternAnalysis(
                pattern=ArchPattern.LAYERED,
                confidence=0.7,
                layers=[[n["id"] for n in layer] for layer in layers],
                evidence=[
                    f"{len(layers)} layer(s) detected",
                    f"{cross_layer_ratio*100:.0f}% cross-layer connections (low = strong layering)",
                ],
            )

    return None


def _detect_peer_mesh(nodes: list[dict], edges: list[dict]) -> Optional[PatternAnalysis]:
    """
    Detect peer-to-peer/mesh pattern.
    Characteristics: bidirectional/many-to-many connections without clear hierarchy.
    """
    if len(nodes) < 2 or len(edges) < 2:
        return None

    # Count bidirectional edges
    bidirectional_count = 0
    edge_set = {(e["source"], e["target"]) for e in edges}

    for source, target in edge_set:
        if (target, source) in edge_set:
            bidirectional_count += 1

    bidirectional_ratio = bidirectional_count / len(edges) if edges else 0

    if bidirectional_ratio > 0.4:  # Many bidirectional edges
        return PatternAnalysis(
            pattern=ArchPattern.PEER_MESH,
            confidence=0.65 + (bidirectional_ratio * 0.25),
            evidence=[
                f"{bidirectional_count} bidirectional connections",
                f"{bidirectional_ratio*100:.0f}% of edges are bidirectional",
            ],
        )

    return None


def detect_pattern(nodes: list[dict], edges: list[dict]) -> PatternAnalysis:
    """
    Detect best-matching architectural pattern.

    Detection priority (checked in order):
    1. Pub-Sub (most specific)
    2. Edge computing (very specific to IoT/edge scenarios)
    3. Gateway hub (clear hub-and-spoke)
    4. Layered (tier-based)
    5. Peer mesh (highly connected)
    6. Client-server (default for request-response)

    Returns PatternAnalysis with pattern, confidence, and evidence.
    Falls back to GENERIC if no strong pattern match.
    """
    # Prioritized detector order for better accuracy
    detectors = [
        _detect_pub_sub,          # Most specific
        _detect_edge_computing,   # Very specific
        _detect_gateway_hub,      # Hub-and-spoke
        _detect_layered,          # Tier-based
        _detect_peer_mesh,        # Many bidirectional
        _detect_client_server,    # Generic request-response (fallback)
    ]

    results = []
    for detector in detectors:
        result = detector(nodes, edges)
        if result and result.confidence > 0.5:
            results.append(result)

    if results:
        # Return highest confidence match
        best = max(results, key=lambda r: r.confidence)
        return best

    return PatternAnalysis(
        pattern=ArchPattern.GENERIC,
        confidence=0.0,
        evidence=["No recognizable pattern detected; using generic layout"],
    )
