"""
visual_orchestrator.py

The brain of the pipeline.  It takes the top recommendation from the
decision engine and dispatches to the correct generator.

It does NOT generate visuals itself — it decides who should.

Dispatch table
--------------
generator == "plantuml"    → call PlantUML MCP server  → SVG
generator == "mermaid"     → render Mermaid inline      → Markdown code block
generator == "browser"     → browser MCP screenshot     → PNG (placeholder)
generator == "filesystem"  → search existing assets     → file path
generator == "none"        → no action

Public API
----------
orchestrate(title, content, section_context=None) -> OrchestratorResult
    Full pipeline: detect → dispatch → return result.

dispatch(recommendation) -> OrchestratorResult
    Dispatch a pre-built recommendation dict directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from analyzers.visual_detector import detect_visuals, compute_signals

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    """Returned by the orchestrator after processing a recommendation."""

    # ── Decision engine output ────────────────
    visual_type: str            # e.g. "Workflow Diagram"
    generator: str              # e.g. "plantuml" | "mermaid" | "browser" | "filesystem" | "none"
    confidence: int             # 0–100
    reason: str                 # Human-readable rationale
    plantuml_code: str | None   # Source code ready to send to PlantUML MCP

    # ── Generator output ──────────────────────
    svg: str | None = None              # Rendered SVG from PlantUML MCP
    mermaid_block: str | None = None    # Mermaid fenced code block
    screenshot_path: str | None = None  # Path to captured screenshot
    existing_asset: str | None = None   # Path to found existing asset

    # ── Pipeline metadata ─────────────────────
    insertion_snippet: str | None = None    # Ready-to-paste Markdown snippet
    status: str = "pending"                 # "ok" | "no_visual" | "error" | "pending"
    error: str | None = None

    # ── Full recommendation (pass-through) ───
    recommendation: dict = field(default_factory=dict)


# ─────────────────────────────────────────────
# Internal dispatcher methods
# ─────────────────────────────────────────────

def _dispatch_plantuml(rec: dict) -> OrchestratorResult:
    """Send PlantUML code to the MCP server and retrieve SVG."""
    from mcp.plantuml_server import render_plantuml  # lazy import

    code = rec.get("plantuml_code")
    if not code:
        return OrchestratorResult(
            visual_type=rec["visual_type"],
            generator="plantuml",
            confidence=rec["confidence"],
            reason=rec["reason"],
            plantuml_code=None,
            status="error",
            error="No PlantUML code was generated for this recommendation.",
            recommendation=rec,
        )

    svg, err = render_plantuml(code)
    return OrchestratorResult(
        visual_type=rec["visual_type"],
        generator="plantuml",
        confidence=rec["confidence"],
        reason=rec["reason"],
        plantuml_code=code,
        svg=svg,
        insertion_snippet=_svg_insertion_snippet(rec["visual_type"], rec.get("placement_hint")),
        status="ok" if svg else "error",
        error=err,
        recommendation=rec,
    )


def _dispatch_mermaid(rec: dict) -> OrchestratorResult:
    """Return the Mermaid code block already embedded in the generated_artifact."""
    artifact = rec.get("generated_artifact") or {}
    mermaid_src = artifact.get("mermaid", "")
    block = f"```mermaid\n{mermaid_src}\n```" if mermaid_src else None

    return OrchestratorResult(
        visual_type=rec["visual_type"],
        generator="mermaid",
        confidence=rec["confidence"],
        reason=rec["reason"],
        plantuml_code=None,
        mermaid_block=block,
        insertion_snippet=block,
        status="ok" if block else "error",
        error=None if block else "No Mermaid code available for this visual type.",
        recommendation=rec,
    )


def _dispatch_browser(rec: dict) -> OrchestratorResult:
    """
    Placeholder for browser MCP integration.
    Returns a result with status 'pending' — the browser MCP is not yet wired.
    """
    return OrchestratorResult(
        visual_type=rec["visual_type"],
        generator="browser",
        confidence=rec["confidence"],
        reason=rec["reason"],
        plantuml_code=None,
        insertion_snippet=rec.get("insertion_snippet"),
        status="pending",
        error="Browser MCP not yet connected.  Capture screenshot manually.",
        recommendation=rec,
    )


def _dispatch_filesystem(rec: dict) -> OrchestratorResult:
    """
    Placeholder for filesystem MCP integration.
    Returns a result with status 'pending' — the filesystem MCP is not yet wired.
    """
    return OrchestratorResult(
        visual_type=rec["visual_type"],
        generator="filesystem",
        confidence=rec["confidence"],
        reason=rec["reason"],
        plantuml_code=None,
        insertion_snippet=rec.get("insertion_snippet"),
        status="pending",
        error="Filesystem MCP not yet connected.  Search asset repository manually.",
        recommendation=rec,
    )


def _dispatch_none(rec: dict) -> OrchestratorResult:
    return OrchestratorResult(
        visual_type=rec["visual_type"],
        generator="none",
        confidence=rec["confidence"],
        reason=rec["reason"],
        plantuml_code=None,
        status="no_visual",
        recommendation=rec,
    )


# ─────────────────────────────────────────────
# Insertion snippet builder
# ─────────────────────────────────────────────

def _svg_insertion_snippet(visual_type: str, placement_hint: dict | None) -> str:
    placement = (
        placement_hint.get("display_text", "At the recommended location")
        if placement_hint else "At the recommended location"
    )
    return (
        f"<!-- Insert {visual_type}: {placement} -->\n"
        "![diagram](../media/generated-diagram.svg)"
    )


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

_DISPATCHERS = {
    "plantuml":   _dispatch_plantuml,
    "mermaid":    _dispatch_mermaid,
    "browser":    _dispatch_browser,
    "filesystem": _dispatch_filesystem,
    "none":       _dispatch_none,
}


def dispatch(recommendation: dict) -> OrchestratorResult:
    """
    Dispatch a single recommendation dict (from detect_visuals) to the
    appropriate generator and return an OrchestratorResult.

    Parameters
    ----------
    recommendation : dict
        A single item from the list returned by detect_visuals().

    Returns
    -------
    OrchestratorResult
    """
    generator = recommendation.get("generator", "none")
    dispatcher = _DISPATCHERS.get(generator, _dispatch_none)
    logger.info(
        "Orchestrator dispatching visual_type=%s to generator=%s",
        recommendation.get("visual_type"),
        generator,
    )
    try:
        return dispatcher(recommendation)
    except Exception as exc:
        logger.error("Orchestrator dispatch failed: %s", exc, exc_info=True)
        return OrchestratorResult(
            visual_type=recommendation.get("visual_type", "Unknown"),
            generator=generator,
            confidence=recommendation.get("confidence", 0),
            reason=recommendation.get("reason", ""),
            plantuml_code=None,
            status="error",
            error=str(exc),
            recommendation=recommendation,
        )


def orchestrate(
    title: str,
    content: str,
    section_context: dict | None = None,
    top_n: int = 1,
) -> list[OrchestratorResult]:
    """
    Full pipeline: detect visuals → dispatch each recommendation.

    Parameters
    ----------
    title : str
        Section heading.
    content : str
        Section body text.
    section_context : dict | None
        Optional adjacent-section context (passed through to detect_visuals).
    top_n : int
        How many recommendations to dispatch (default 1 — the top pick only).

    Returns
    -------
    list[OrchestratorResult]
        One result per dispatched recommendation.
    """
    recommendations = detect_visuals(title, content, section_context)
    results = []
    for rec in recommendations[:top_n]:
        results.append(dispatch(rec))
    return results
