#!/usr/bin/env python3
"""DOCX export MCP server — stdio transport.

Exposes two tools:
  docx_from_markdown(input, output[, reference_doc])
  docx_to_markdown(input, output)

All tools return TextContent carrying JSON in the locked contract:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# ---------------------------------------------------------------------------
# Paths — derived from running interpreter; no hardcoded personal paths
# ---------------------------------------------------------------------------

_ENV_PYTHON = sys.executable
_CONDA_BIN = os.path.dirname(sys.executable)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCX_TOOL = _REPO_ROOT / "tools" / "docx_tool.py"
_SUBPROCESS_PATH = f"{_CONDA_BIN}:/usr/bin:/bin"

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("docx-mcp")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _err(error: str, stderr: str = "") -> list[types.TextContent]:
    payload = {"success": False, "error": error, "stderr": stderr}
    return [types.TextContent(type="text", text=json.dumps(payload))]


def _run_tool(args: list[str]) -> list[types.TextContent]:
    """Subprocess docx_tool.py with the given args; parse and return its JSON."""
    cmd = [_ENV_PYTHON, str(_DOCX_TOOL)] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        env={"PATH": _SUBPROCESS_PATH},
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return _err("docx_tool.py returned non-JSON output", result.stderr)
    return [types.TextContent(type="text", text=json.dumps(data))]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="docx_from_markdown",
            description=(
                "Convert a Markdown file to .docx using pandoc. "
                "Optionally apply a reference .docx for custom styling."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Path to the Markdown source file.",
                    },
                    "output": {
                        "type": "string",
                        "description": "Path for the output .docx file (parent dirs created automatically).",
                    },
                    "reference_doc": {
                        "type": "string",
                        "description": "Optional path to a .docx reference document for styling.",
                    },
                },
                "required": ["input", "output"],
            },
        ),
        types.Tool(
            name="docx_to_markdown",
            description="Convert a .docx file to Markdown using pandoc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Path to the .docx source file.",
                    },
                    "output": {
                        "type": "string",
                        "description": "Path for the output Markdown file.",
                    },
                },
                "required": ["input", "output"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "docx_from_markdown":
        return _handle_from_markdown(arguments)
    if name == "docx_to_markdown":
        return _handle_to_markdown(arguments)
    return _err(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _handle_from_markdown(args: dict) -> list[types.TextContent]:
    input_file = args.get("input", "")
    output_file = args.get("output", "")

    if not input_file:
        return _err("Missing required argument: input")
    if not output_file:
        return _err("Missing required argument: output")

    cmd_args = ["from-markdown", "--input", input_file, "--output", output_file]
    if args.get("reference_doc"):
        cmd_args += ["--reference-doc", args["reference_doc"]]
    return _run_tool(cmd_args)


def _handle_to_markdown(args: dict) -> list[types.TextContent]:
    input_file = args.get("input", "")
    output_file = args.get("output", "")

    if not input_file:
        return _err("Missing required argument: input")
    if not output_file:
        return _err("Missing required argument: output")

    return _run_tool(["to-markdown", "--input", input_file, "--output", output_file])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
