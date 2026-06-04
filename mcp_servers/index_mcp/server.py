#!/usr/bin/env python3
"""Workspace indexing MCP server — stdio transport.

Exposes two tools:
  index_build(dir?)          Build/refresh the FTS5 index over a directory.
  index_search(query, limit?) Search the index, return ranked paths + snippets.

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
_INDEX_TOOL = _REPO_ROOT / "tools" / "index_tool.py"
_SUBPROCESS_PATH = f"{_CONDA_BIN}:/usr/bin:/bin"

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("index-mcp")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(output: str, meta: dict) -> list[types.TextContent]:
    payload = {"success": True, "output": output, "meta": meta}
    return [types.TextContent(type="text", text=json.dumps(payload))]


def _err(error: str, stderr: str = "") -> list[types.TextContent]:
    payload = {"success": False, "error": error, "stderr": stderr}
    return [types.TextContent(type="text", text=json.dumps(payload))]


def _run_tool(args: list[str]) -> list[types.TextContent]:
    """Subprocess index_tool.py with the given args; parse and return its JSON."""
    cmd = [_ENV_PYTHON, str(_INDEX_TOOL)] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        env={"PATH": _SUBPROCESS_PATH},
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return _err("index_tool.py returned non-JSON output", result.stderr)
    return [types.TextContent(type="text", text=json.dumps(data))]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="index_build",
            description=(
                "Scan a directory and build (or refresh) the FTS5 workspace index at "
                "workspace/index.db. Extracts text from .md, .qmd, .tex, .txt, and .pdf files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dir": {
                        "type": "string",
                        "description": "Directory to index (default: workspace/).",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="index_search",
            description=(
                "Search the workspace index using an FTS5 query. Returns ranked results "
                "with file paths and text snippets."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "FTS5 search query (e.g. 'quarto slides').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10).",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "index_build":
        return _handle_build(arguments)
    if name == "index_search":
        return _handle_search(arguments)
    return _err(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _handle_build(args: dict) -> list[types.TextContent]:
    cmd_args = ["build"]
    if args.get("dir"):
        cmd_args += ["--dir", args["dir"]]
    return _run_tool(cmd_args)


def _handle_search(args: dict) -> list[types.TextContent]:
    query = args.get("query", "")
    if not query:
        return _err("Missing required argument: query")

    cmd_args = ["search", "--query", query]
    if args.get("limit"):
        cmd_args += ["--limit", str(args["limit"])]
    return _run_tool(cmd_args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
