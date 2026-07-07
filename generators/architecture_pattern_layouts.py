"""
Pattern-specific layout algorithms for architecture diagrams.

Each pattern has different visualization goals:
- CLIENT_SERVER: horizontal flow left→right
- EDGE_COMPUTING: vertical flow bottom→top
- GATEWAY_HUB: radial layout around central hub
- PUB_SUB: three-column layout (publishers | broker | subscribers)
- LAYERED: strict horizontal tiers
- PEER_MESH: circular/force-directed layout
"""

from typing import Optional, Dict, Tuple
import math
from generators.architecture_patterns import ArchPattern


class PatternLayout:
    """Base layout strategy."""

    def __init__(self, nodes: list[dict], edges: list[dict], width: int = 1200, height: int = 900):
        self.nodes = nodes
        self.edges = edges
        self.width = width
        self.height = height
        self.positions: Dict[str, Tuple[float, float]] = {}
        self.containers: Dict[str, dict] = {}  # node_id -> container info

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        """Compute node positions. Override in subclass."""
        return self._default_layout()

    def _default_layout(self) -> Dict[str, Tuple[float, float]]:
        """Fallback: spread nodes evenly."""
        positions = {}
        n = len(self.nodes)
        for i, node in enumerate(self.nodes):
            angle = (2 * math.pi * i) / n if n > 0 else 0
            r = 300
            x = self.width // 2 + r * math.cos(angle)
            y = self.height // 2 + r * math.sin(angle)
            positions[node["id"]] = (x, y)
        self.positions = positions
        return positions


class ClientServerLayout(PatternLayout):
    """Client on left, server on right."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}
        clients = []
        servers = []

        for node in self.nodes:
            if node["type"] in ["interface", "application", "device", "runtime", "connector", "ui"]:
                clients.append(node)
            else:
                servers.append(node)

        # Fallback if everything was grouped into one side
        if not clients and len(servers) > 1:
            clients = servers[:len(servers)//2]
            servers = servers[len(servers)//2:]
        elif not servers and len(clients) > 1:
            servers = clients[:len(clients)//2]
            clients = clients[len(clients)//2:]

        margin_x = 150
        margin_y = 100
        client_x = margin_x + 100
        server_x = self.width - margin_x - 100

        # Distribute clients vertically
        client_spacing = (self.height - 2 * margin_y) / max(1, len(clients)) if clients else 0
        for i, node in enumerate(clients):
            y = margin_y + i * client_spacing + client_spacing / 2
            positions[node["id"]] = (client_x, y)

        # Distribute servers vertically
        server_spacing = (self.height - 2 * margin_y) / max(1, len(servers)) if servers else 0
        for i, node in enumerate(servers):
            y = margin_y + i * server_spacing + server_spacing / 2
            positions[node["id"]] = (server_x, y)

        self.positions = positions
        return positions


class EdgeComputingLayout(PatternLayout):
    """Edge devices at bottom, cloud at top."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}
        edge_nodes = []
        cloud_nodes = []

        for node in self.nodes:
            if node["type"] in ["device", "runtime", "application"]:
                edge_nodes.append(node)
            else:
                cloud_nodes.append(node)

        # Cloud at top
        cloud_y = 150
        cloud_spacing = (self.width - 300) / max(1, len(cloud_nodes)) if cloud_nodes else 0
        for i, node in enumerate(cloud_nodes):
            x = 150 + i * cloud_spacing + cloud_spacing / 2
            positions[node["id"]] = (x, cloud_y)

        # Edge at bottom
        edge_y = self.height - 150
        edge_spacing = (self.width - 300) / max(1, len(edge_nodes)) if edge_nodes else 0
        for i, node in enumerate(edge_nodes):
            x = 150 + i * edge_spacing + edge_spacing / 2
            positions[node["id"]] = (x, edge_y)

        self.positions = positions
        return positions


class GatewayHubLayout(PatternLayout):
    """Gateway in center, peers arranged in circle."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}
        hub_node = None
        spoke_nodes = []

        # Identify hub (highest degree node or explicit gateway)
        for node in self.nodes:
            in_deg = sum(1 for e in self.edges if e["target"] == node["id"])
            out_deg = sum(1 for e in self.edges if e["source"] == node["id"])
            if in_deg + out_deg == max(
                sum(1 for e in self.edges if e["target"] == n["id"]) +
                sum(1 for e in self.edges if e["source"] == n["id"])
                for n in self.nodes
            ):
                hub_node = node
                break

        if not hub_node:
            hub_node = self.nodes[0]

        spoke_nodes = [n for n in self.nodes if n["id"] != hub_node["id"]]

        # Hub in center
        hub_x, hub_y = self.width // 2, self.height // 2
        positions[hub_node["id"]] = (hub_x, hub_y)

        # Spokes in circle around hub
        radius = min(self.width, self.height) // 3
        for i, node in enumerate(spoke_nodes):
            angle = (2 * math.pi * i) / max(1, len(spoke_nodes))
            x = hub_x + radius * math.cos(angle)
            y = hub_y + radius * math.sin(angle)
            positions[node["id"]] = (x, y)

        self.positions = positions
        return positions


class PubSubLayout(PatternLayout):
    """Publishers left, broker middle, subscribers right."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}
        publishers = []
        subscribers = []
        broker = None

        # Identify broker (node with both incoming publish and outgoing subscribe edges)
        for node in self.nodes:
            pub_in = sum(1 for e in self.edges if e["target"] == node["id"] and "publish" in str(e.get("type", "")).lower())
            sub_out = sum(1 for e in self.edges if e["source"] == node["id"] and "subscribe" in str(e.get("type", "")).lower())
            if pub_in > 0 and sub_out > 0:
                broker = node
                break

        if not broker and self.nodes:
            broker = self.nodes[0]

        # Classify remaining nodes
        for node in self.nodes:
            if node["id"] == broker["id"]:
                continue
            # Simple heuristic: publishers vs subscribers based on edge direction
            out_deg = sum(1 for e in self.edges if e["source"] == node["id"])
            in_deg = sum(1 for e in self.edges if e["target"] == node["id"])
            if out_deg >= in_deg:
                publishers.append(node)
            else:
                subscribers.append(node)

        if not publishers and not subscribers and self.nodes:
            publishers = self.nodes[:len(self.nodes)//2]
            subscribers = self.nodes[len(self.nodes)//2:]

        # Three columns
        broker_x = self.width // 2
        broker_y = self.height // 2
        positions[broker["id"]] = (broker_x, broker_y)

        pub_x = 200
        pub_spacing = (self.height - 300) / max(1, len(publishers)) if publishers else 0
        for i, node in enumerate(publishers):
            y = 150 + i * pub_spacing + pub_spacing / 2
            positions[node["id"]] = (pub_x, y)

        sub_x = self.width - 200
        sub_spacing = (self.height - 300) / max(1, len(subscribers)) if subscribers else 0
        for i, node in enumerate(subscribers):
            y = 150 + i * sub_spacing + sub_spacing / 2
            positions[node["id"]] = (sub_x, y)

        self.positions = positions
        return positions


class LayeredLayout(PatternLayout):
    """Strict horizontal layers."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}

        # Compute layer for each node based on in-degree
        layers: Dict[int, list] = {}
        for node in self.nodes:
            in_deg = sum(1 for e in self.edges if e["target"] == node["id"])
            layer = in_deg
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(node)

        # Sort layers
        sorted_layers = sorted(layers.keys())

        # Assign y positions by layer
        layer_height = self.height / max(1, len(sorted_layers))
        for layer_idx, layer_num in enumerate(sorted_layers):
            y = 100 + layer_idx * layer_height
            nodes_in_layer = layers[layer_num]
            x_spacing = (self.width - 300) / max(1, len(nodes_in_layer)) if nodes_in_layer else 0
            for i, node in enumerate(nodes_in_layer):
                x = 150 + i * x_spacing + x_spacing / 2
                positions[node["id"]] = (x, y)

        self.positions = positions
        return positions


class PeerMeshLayout(PatternLayout):
    """Circular arrangement for peer-to-peer."""

    def compute_positions(self) -> Dict[str, Tuple[float, float]]:
        positions = {}
        radius = min(self.width, self.height) // 3

        for i, node in enumerate(self.nodes):
            angle = (2 * math.pi * i) / max(1, len(self.nodes))
            x = self.width // 2 + radius * math.cos(angle)
            y = self.height // 2 + radius * math.sin(angle)
            positions[node["id"]] = (x, y)

        self.positions = positions
        return positions


def create_layout(pattern: ArchPattern, nodes: list[dict], edges: list[dict], width: int = 1200, height: int = 900) -> PatternLayout:
    """Factory function to create appropriate layout for pattern."""
    layouts = {
        ArchPattern.CLIENT_SERVER: ClientServerLayout,
        ArchPattern.EDGE_COMPUTING: EdgeComputingLayout,
        ArchPattern.GATEWAY_HUB: GatewayHubLayout,
        ArchPattern.PUB_SUB: PubSubLayout,
        ArchPattern.LAYERED: LayeredLayout,
        ArchPattern.PEER_MESH: PeerMeshLayout,
    }

    layout_class = layouts.get(pattern, PatternLayout)
    return layout_class(nodes, edges, width, height)
