#!/usr/bin/env python3
"""Quarto MCP server — stdio transport.

Exposes three tools:
  quarto_render(input, format[, output_dir])
  quarto_create(template, output_dir)
  quarto_check()

All tools return TextContent carrying JSON in the locked contract:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Paths — derived from the running interpreter so no hardcoded user paths
# ---------------------------------------------------------------------------

_ENV_PYTHON = sys.executable                        # e.g. .../envs/office-suite/bin/python
_CONDA_BIN = os.path.dirname(sys.executable)        # e.g. .../envs/office-suite/bin
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SLIDES_TOOL = _REPO_ROOT / "tools" / "slides_tool.py"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "quarto"
_WORKSPACE_DIR = _REPO_ROOT / "workspace"

# PATH that guarantees quarto and standard tools are found
_SUBPROCESS_PATH = f"{_CONDA_BIN}:/usr/bin:/bin"

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("quarto-mcp")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(output: str, meta: dict) -> list[types.TextContent]:
    payload = {"success": True, "output": output, "meta": meta}
    return [types.TextContent(type="text", text=json.dumps(payload))]


def _err(error: str, stderr: str = "") -> list[types.TextContent]:
    payload = {"success": False, "error": error, "stderr": stderr}
    return [types.TextContent(type="text", text=json.dumps(payload))]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="quarto_render",
            description="Render a .qmd file to revealjs, pdf, or pptx via Quarto.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Path to the .qmd source file.",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["revealjs", "pdf", "pptx"],
                        "description": "Output format.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory (defaults to same dir as input).",
                    },
                },
                "required": ["input", "format"],
            },
        ),
        types.Tool(
            name="quarto_create",
            description="Copy a Quarto template into the workspace, ready for editing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Template name (file stem, e.g. 'slides'). Must exist in templates/quarto/.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Sub-directory under workspace/ to copy the template into.",
                    },
                },
                "required": ["template", "output_dir"],
            },
        ),
        types.Tool(
            name="quarto_check",
            description="Run 'quarto check' and return version and installation status.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "quarto_render":
        return await _quarto_render(arguments)
    if name == "quarto_create":
        return await _quarto_create(arguments)
    if name == "quarto_check":
        return await _quarto_check()
    return _err(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _quarto_render(args: dict) -> list[types.TextContent]:
    input_file = args.get("input", "")
    fmt = args.get("format", "")
    output_dir = args.get("output_dir")

    if not input_file:
        return _err("Missing required argument: input")
    if fmt not in ("revealjs", "pdf", "pptx"):
        return _err(f"Invalid format: {fmt!r}. Must be one of: revealjs, pdf, pptx")

    cmd = [
        _ENV_PYTHON,
        str(_SLIDES_TOOL),
        "render",
        "--input", input_file,
        "--format", fmt,
    ]
    if output_dir:
        cmd += ["--output-dir", output_dir]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        env={"PATH": _SUBPROCESS_PATH},
    )

    # slides_tool.py always writes valid JSON to stdout
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return _err("slides_tool.py returned non-JSON output", result.stderr)

    return [types.TextContent(type="text", text=json.dumps(data))]


async def _quarto_create(args: dict) -> list[types.TextContent]:
    template_name = args.get("template", "")
    output_dir = args.get("output_dir", "")

    if not template_name:
        return _err("Missing required argument: template")
    if not output_dir:
        return _err("Missing required argument: output_dir")

    # Locate template file (accept with or without .qmd extension)
    src = _TEMPLATES_DIR / f"{template_name}.qmd"
    if not src.exists():
        src = _TEMPLATES_DIR / template_name
    if not src.exists():
        return _err(
            f"Template not found: {template_name!r} (looked in {_TEMPLATES_DIR})",
            "",
        )

    dest_dir = _WORKSPACE_DIR / output_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    shutil.copy2(src, dest)

    return _ok(
        str(dest),
        {"template": template_name, "size_bytes": dest.stat().st_size},
    )


async def _quarto_check() -> list[types.TextContent]:
    result = subprocess.run(
        ["quarto", "check"],
        capture_output=True,
        text=True,
        env={"PATH": _SUBPROCESS_PATH},
    )

    combined = (result.stdout + result.stderr).strip()

    if result.returncode != 0:
        return _err("quarto check failed", combined)

    # Extract version from output when present ("Quarto 1.x.y")
    version = ""
    for line in combined.splitlines():
        if line.strip().startswith("Quarto"):
            version = line.strip()
            break

    return _ok("quarto check passed", {"version": version, "output": combined})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
