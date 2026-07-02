"""Semantic layout engine for architecture diagrams."""


class ArchitectureLayout:
    """Compute semantic positions, containers, and sizing for architecture diagrams."""

    def __init__(self, nodes: list[dict], edges: list[dict]):
        self.nodes = nodes
        self.edges = edges

    def _get_node_type_rank(self, node_type: str) -> int:
        type_ranks = {
            "cloud": 0,
            "external_system": 0,
            "server": 1,
            "system": 1,
            "database": 1,
            "gateway": 2,
            "network_component": 2,
            "application": 3,
            "runtime": 3,
            "interface": 3,
            "device": 4,
        }
        return type_ranks.get(node_type, 2)

    def _is_containment_edge(self, edge: dict) -> bool:
        if edge.get("semantic") == "containment":
            return True
        return edge.get("type") in {"runs_on", "installed_on", "hosted_on", "deployed_on", "client_on", "contains"}

    def _infer_containment(self) -> dict[str, str]:
        """Return child->parent map from explicit and light heuristic containment."""
        node_by_id = {node["id"]: node for node in self.nodes}
        parent_by_child: dict[str, str] = {}

        for edge in self.edges:
            if not self._is_containment_edge(edge):
                continue
            source = edge.get("source")
            target = edge.get("target")
            if source in node_by_id and target in node_by_id and source != target:
                parent_by_child[source] = target

        # Heuristic: application/runtime/interface likely lives inside device/gateway/server.
        child_types = {"application", "runtime", "interface"}
        parent_types = {"device", "gateway", "network_component", "server", "system"}

        for node in self.nodes:
            child_id = node["id"]
            if child_id in parent_by_child:
                continue
            if node.get("type") not in child_types:
                continue

            candidates = [
                parent for parent in self.nodes
                if parent["id"] != child_id and parent.get("type") in parent_types
            ]
            if len(candidates) == 1:
                parent_by_child[child_id] = candidates[0]["id"]

        return parent_by_child

    def _compute_layer_assignments(self, top_nodes: list[dict], non_containment_edges: list[dict]) -> dict[str, int]:
        layers = {node["id"]: self._get_node_type_rank(node.get("type", "application")) for node in top_nodes}
        valid_ids = set(layers.keys())

        changed = True
        max_iterations = 10
        iterations = 0
        while changed and iterations < max_iterations:
            changed = False
            iterations += 1
            for edge in non_containment_edges:
                source = edge.get("source")
                target = edge.get("target")
                if source not in valid_ids or target not in valid_ids:
                    continue
                if layers[source] >= layers[target]:
                    layers[target] = layers[source] + 1
                    changed = True
        return layers

    def compute_layout(self, canvas_width: int = 1280, canvas_height: int = 920) -> dict:
        """Compute full semantic layout model for rendering."""
        parent_by_child = self._infer_containment()
        children_by_parent: dict[str, list[str]] = {}
        for child, parent in parent_by_child.items():
            children_by_parent.setdefault(parent, []).append(child)

        child_ids = set(parent_by_child.keys())
        top_nodes = [node for node in self.nodes if node["id"] not in child_ids]

        non_containment_edges = [edge for edge in self.edges if not self._is_containment_edge(edge)]
        layers = self._compute_layer_assignments(top_nodes, non_containment_edges)

        layer_nodes: dict[int, list[str]] = {}
        for node_id, layer in layers.items():
            layer_nodes.setdefault(layer, []).append(node_id)

        positions: dict[str, tuple[float, float]] = {}
        hidden_nodes: set[str] = set()
        containers: list[dict] = []

        sorted_layers = sorted(layer_nodes.keys())
        title_space = 120
        legend_space = 130
        top_margin = title_space + 20
        bottom_margin = legend_space
        initial_margin = 80
        base_node_width = max(190, min(320, int((canvas_width - initial_margin * 2) / 3.0)))
        base_node_height = 96
        left_margin = (base_node_width / 2) + 28
        right_margin = (base_node_width / 2) + 28

        if sorted_layers:
            vertical_space = max(1, canvas_height - top_margin - bottom_margin)
            vertical_step = vertical_space / max(1, len(sorted_layers))
        else:
            vertical_step = canvas_height / 2

        for idx, layer in enumerate(sorted_layers):
            node_ids = sorted(layer_nodes[layer])
            y = top_margin + (idx + 0.5) * vertical_step
            count = len(node_ids)
            if count == 1:
                positions[node_ids[0]] = (canvas_width / 2, y)
                continue

            usable_width = canvas_width - left_margin - right_margin
            step_x = usable_width / (count - 1)
            for node_idx, node_id in enumerate(node_ids):
                x = left_margin + node_idx * step_x
                positions[node_id] = (x, y)

        node_sizes = {node["id"]: (base_node_width, base_node_height) for node in self.nodes}
        node_by_id = {node["id"]: node for node in self.nodes}

        for parent_id, child_list in children_by_parent.items():
            if parent_id not in positions:
                continue

            parent_x, parent_y = positions[parent_id]
            children = sorted(child_list)
            child_count = len(children)
            child_w = max(170, int(base_node_width * 0.85))
            child_h = max(80, int(base_node_height * 0.88))
            node_sizes[parent_id] = (max(base_node_width, int(base_node_width * 1.1)), base_node_height)

            container_padding = 32
            header_height = 42
            row_gap = 16
            container_inner_h = child_count * child_h + max(0, child_count - 1) * row_gap
            container_w = max(base_node_width + 100, child_w + container_padding * 2)
            container_h = max(180, header_height + container_inner_h + container_padding)

            container_x = parent_x - container_w / 2
            container_y = parent_y - container_h / 2

            # Keep container fully visible in canvas.
            if container_x < 24:
                delta = 24 - container_x
                parent_x += delta
                container_x = 24
            if container_x + container_w > canvas_width - 24:
                delta = (container_x + container_w) - (canvas_width - 24)
                parent_x -= delta
                container_x -= delta

            start_y = container_y + header_height + container_padding / 2 + child_h / 2
            for idx, child_id in enumerate(children):
                child_y = start_y + idx * (child_h + row_gap)
                positions[child_id] = (parent_x, child_y)
                node_sizes[child_id] = (child_w, child_h)

            hidden_nodes.add(parent_id)
            parent_node = node_by_id[parent_id]
            containers.append(
                {
                    "id": parent_id,
                    "label": parent_node.get("name", parent_id),
                    "type": parent_node.get("type", "device"),
                    "x": container_x,
                    "y": container_y,
                    "width": container_w,
                    "height": container_h,
                    "header_height": header_height,
                    "children": children,
                    "anchor": (parent_x, parent_y),
                }
            )

        return {
            "positions": positions,
            "node_sizes": node_sizes,
            "containers": containers,
            "hidden_nodes": sorted(hidden_nodes),
            "canvas": {"width": canvas_width, "height": canvas_height},
            "edges": non_containment_edges,
        }
