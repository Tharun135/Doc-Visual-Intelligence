"""Architecture diagram generation pipeline orchestrator."""

from typing import Optional
from generators.architecture_parser import parse_section_for_architecture
from generators.architecture_patterns import detect_pattern
from generators.architecture_pattern_layouts import create_layout
from generators.architecture_renderer import generate_architecture_svg


def generate_architecture_diagram(section_title: str, section_content: str) -> Optional[str]:
    """
    Generate an architecture diagram SVG from a documentation section.

    Pipeline:
    1. Parse section for architecture content (extract components + relationships)
    2. Detect architectural pattern (client-server, edge, gateway, pub-sub, etc.)
    3. Choose pattern-specific layout strategy
    4. Compute node positions
    5. Render SVG with semantic awareness

    Returns SVG string or None if no architecture detected.
    """
    # Step 1: Parse section
    arch_model = parse_section_for_architecture(section_title, section_content, force_parse=True)

    if not arch_model:
        return None

    # Step 2: Extract components and relationships
    nodes = arch_model.get("nodes", [])
    edges = arch_model.get("edges", [])

    if not nodes or not edges:
        return None

    # Step 3: Detect architectural pattern
    pattern_analysis = detect_pattern(nodes, edges)

    # Step 4: Create pattern-specific layout
    layout = create_layout(pattern_analysis.pattern, nodes, edges, width=1280, height=920)
    positions = layout.compute_positions()

    # Step 5: Render SVG with pattern metadata
    title = arch_model.get("title", "System Architecture")
    svg = generate_architecture_svg(
        title, nodes, edges, positions,
        width=1280, height=920,
        pattern=pattern_analysis
    )

    return svg


def batch_generate_architecture_diagrams(sections: list[dict]) -> list[dict]:
    """
    Generate architecture diagrams from all sections.

    Args:
        sections: List of {"title", "content"} dicts

    Returns:
        List of {"title", "svg", "entities_found", "relationships_found"} dicts
    """
    diagrams = []

    for section in sections:
        title = section.get("title", "")
        content = section.get("content", "")

        svg = generate_architecture_diagram(title, content)
        if svg:
            # Parse to get stats
            arch_model = parse_section_for_architecture(title, content)
            diagrams.append(
                {
                    "title": title,
                    "svg": svg,
                    "entities_found": arch_model.get("entities_found", 0),
                    "relationships_found": arch_model.get("relationships_found", 0),
                }
            )

    return diagrams
