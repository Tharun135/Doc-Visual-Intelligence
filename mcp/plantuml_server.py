"""
plantuml_server.py — PlantUML MCP server

Provides two interfaces:

1. render_plantuml(code) -> (svg | None, error | None)
   Python function — called directly by the orchestrator.

2. MCP tool: render_plantuml_tool
   Exposes the same capability as an MCP-compatible tool definition
   so that an MCP host (VS Code agent, Claude Desktop, etc.) can
   call it over the stdio/HTTP transport.

Rendering strategy
------------------
Priority 1: Local PlantUML JAR (PLANTUML_JAR env var or plantuml.jar in project root)
Priority 2: PlantUML public API (https://www.plantuml.com/plantuml/svg/...)
Priority 3: Error — neither available

PlantUML encoding for the public API uses the standard deflate + base64
variant defined at https://plantuml.com/code-javascript-asynchronous
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import tempfile
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# PlantUML public-API encoding
# ─────────────────────────────────────────────

_PLANTUML_CHARS = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
)


def _encode_6bit(b: int) -> str:
    return _PLANTUML_CHARS[b & 0x3F]


def _append_3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return (
        _encode_6bit(c1)
        + _encode_6bit(c2)
        + _encode_6bit(c3)
        + _encode_6bit(c4)
    )


def _plantuml_encode(source: str) -> str:
    """Encode PlantUML source for use in the public REST API URL."""
    data = zlib.compress(source.encode("utf-8"), 9)[2:-4]  # strip zlib header/checksum
    result = []
    i = 0
    while i < len(data):
        b1 = data[i]
        b2 = data[i + 1] if i + 1 < len(data) else 0
        b3 = data[i + 2] if i + 2 < len(data) else 0
        result.append(_append_3bytes(b1, b2, b3))
        i += 3
    return "".join(result)


# ─────────────────────────────────────────────
# Rendering backends
# ─────────────────────────────────────────────

def _render_via_jar(code: str, jar_path: Path) -> tuple[str | None, str | None]:
    """Render PlantUML code using a local JAR file.  Returns (svg_str, error)."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "diagram.puml"
            src_file.write_text(code, encoding="utf-8")

            result = subprocess.run(
                ["java", "-jar", str(jar_path), "-tsvg", "-charset", "UTF-8", str(src_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return None, f"PlantUML JAR error: {result.stderr.strip()}"

            svg_file = Path(tmpdir) / "diagram.svg"
            if svg_file.exists():
                return svg_file.read_text(encoding="utf-8"), None

            return None, "PlantUML JAR ran but produced no SVG file."

    except FileNotFoundError:
        return None, "java is not installed or not on PATH."
    except subprocess.TimeoutExpired:
        return None, "PlantUML JAR timed out after 30 seconds."
    except Exception as exc:
        return None, f"Unexpected error running PlantUML JAR: {exc}"


def _render_via_api(code: str) -> tuple[str | None, str | None]:
    """Render PlantUML code via the public plantuml.com API.  Returns (svg_str, error)."""
    try:
        import urllib.request  # stdlib — no extra dependency

        encoded = _plantuml_encode(code)
        url = f"https://www.plantuml.com/plantuml/svg/{encoded}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Doc-Visual-Intelligence/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            svg = response.read().decode("utf-8")

        # Validate we actually received SVG
        if "<svg" not in svg:
            return None, f"PlantUML API returned unexpected content: {svg[:200]}"

        return svg, None

    except Exception as exc:
        return None, f"PlantUML API request failed: {exc}"


# ─────────────────────────────────────────────
# Public render function (called by orchestrator)
# ─────────────────────────────────────────────

def render_plantuml(code: str) -> tuple[str | None, str | None]:
    """
    Render PlantUML source code to SVG.

    Tries local JAR first, then falls back to the public API.

    Parameters
    ----------
    code : str
        Valid PlantUML source (@startuml … @enduml).

    Returns
    -------
    (svg, error) : tuple[str | None, str | None]
        On success:  (svg_string, None)
        On failure:  (None, error_message)
    """
    if not code or not code.strip():
        return None, "Empty PlantUML code provided."

    # Priority 1: local JAR
    jar_env = os.environ.get("PLANTUML_JAR", "")
    project_jar = Path(__file__).parent.parent / "plantuml.jar"

    if jar_env and Path(jar_env).is_file():
        logger.info("Rendering via local JAR: %s", jar_env)
        svg, err = _render_via_jar(code, Path(jar_env))
        if svg:
            return svg, None
        logger.warning("JAR render failed (%s), falling back to API.", err)

    elif project_jar.is_file():
        logger.info("Rendering via project JAR: %s", project_jar)
        svg, err = _render_via_jar(code, project_jar)
        if svg:
            return svg, None
        logger.warning("JAR render failed (%s), falling back to API.", err)

    # Priority 2: public API
    logger.info("Rendering via PlantUML public API.")
    return _render_via_api(code)


# ─────────────────────────────────────────────
# MCP tool definition
# ─────────────────────────────────────────────

MCP_TOOL_DEFINITION = {
    "name": "render_plantuml",
    "description": (
        "Render a PlantUML diagram from source code and return an SVG string. "
        "Tries a local PlantUML JAR first (PLANTUML_JAR env var or plantuml.jar "
        "in the project root), then falls back to the public plantuml.com API."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Valid PlantUML source code beginning with @startuml and ending with @enduml.",
            }
        },
        "required": ["code"],
    },
}


def handle_mcp_call(tool_name: str, arguments: dict) -> dict:
    """
    Handle an incoming MCP tool call.

    Parameters
    ----------
    tool_name : str
        Must be "render_plantuml".
    arguments : dict
        Must contain "code" key.

    Returns
    -------
    dict
        MCP-compatible content response with "type", "text" keys.
    """
    if tool_name != "render_plantuml":
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
        }

    code = arguments.get("code", "").strip()
    if not code:
        return {
            "isError": True,
            "content": [{"type": "text", "text": "Missing required argument: code"}],
        }

    svg, error = render_plantuml(code)

    if error:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Render failed: {error}"}],
        }

    return {
        "isError": False,
        "content": [{"type": "text", "text": svg}],
    }


# ─────────────────────────────────────────────
# Stdio MCP server entry point
# ─────────────────────────────────────────────

def run_stdio_server() -> None:
    """
    Run this module as a stdio-based MCP server.

    The server reads JSON-RPC 2.0 messages from stdin and writes
    responses to stdout, conforming to the MCP specification.

    Start with:
        python -m mcp.plantuml_server
    """
    import sys

    _send = lambda obj: (sys.stdout.write(json.dumps(obj) + "\n"), sys.stdout.flush())

    logger.info("PlantUML MCP server started (stdio transport).")

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            _send({"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {exc}"}, "id": None})
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")

        # ── Capability handshake ───────────────
        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "plantuml-mcp", "version": "1.0.0"},
                },
            })

        elif method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": [MCP_TOOL_DEFINITION]},
            })

        elif method == "tools/call":
            params = msg.get("params", {})
            result = handle_mcp_call(params.get("name", ""), params.get("arguments", {}))
            _send({"jsonrpc": "2.0", "id": msg_id, "result": result})

        else:
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_stdio_server()
