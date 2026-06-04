#!/usr/bin/env python3
"""Smoke test for index-mcp server.

Tests:
  1. Server module imports without error.
  2. list_tools() returns both expected tools.
  3. index_build over a temp dir with two files succeeds (indexed >= 2).
  4. index_search for "quarto" returns the quarto file in results.
"""

import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


def _assert(condition: bool, msg: str):
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


async def run_tests():
    # ------------------------------------------------------------------
    # Test 1: import server module
    # ------------------------------------------------------------------
    print("Test 1: import server module")
    spec = importlib.util.spec_from_file_location(
        "index_mcp_server",
        Path(__file__).resolve().parent / "server.py",
    )
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    srv = server_mod.server
    print("  ok: server module imported")

    # ------------------------------------------------------------------
    # Test 2: list_tools
    # ------------------------------------------------------------------
    print("Test 2: list_tools")
    from mcp import types

    handler = srv.request_handlers.get(types.ListToolsRequest)
    _assert(handler is not None, "ListToolsRequest handler registered")

    result = await handler(types.ListToolsRequest(method="tools/list", params=None))
    tool_names = {t.name for t in result.root.tools}
    expected = {"index_build", "index_search"}
    _assert(expected == tool_names, f"tools listed correctly (got {tool_names})")

    # ------------------------------------------------------------------
    # Test 3: index_build over a temp dir
    # ------------------------------------------------------------------
    print("Test 3: index_build")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Two files — each clearly about a distinct topic
        (tmp / "about_quarto.txt").write_text(
            "Quarto is a scientific publishing system built on Pandoc. "
            "It supports revealjs slides and PDF output.",
            encoding="utf-8",
        )
        (tmp / "about_latex.txt").write_text(
            "LaTeX is a typesetting system widely used for academic papers. "
            "It produces high-quality PDF documents.",
            encoding="utf-8",
        )

        # Use a temp DB so we don't pollute workspace/index.db
        db_path = tmp / "test_index.db"

        content_list = server_mod._handle_build({
            "dir": str(tmp),
            # Pass db via the underlying CLI --db flag by calling _run_tool directly
        })

        # Re-call with explicit db so search uses the same temp DB
        # (The default _handle_build uses workspace/index.db; override via _run_tool)
        content_list = server_mod._run_tool([
            "build", "--dir", str(tmp), "--db", str(db_path),
        ])

        _assert(len(content_list) == 1, "got one TextContent item from build")
        payload = json.loads(content_list[0].text)
        _assert(payload.get("success") is True, f"build success=true (payload: {payload})")
        indexed = payload["meta"]["indexed"]
        _assert(indexed >= 2, f"indexed >= 2 files (got {indexed})")
        print(f"  indexed: {indexed} files, skipped: {payload['meta']['skipped']}")

        # ------------------------------------------------------------------
        # Test 4: index_search for "quarto"
        # ------------------------------------------------------------------
        print("Test 4: index_search for 'quarto'")
        content_list = server_mod._run_tool([
            "search", "--query", "quarto", "--db", str(db_path),
        ])

        _assert(len(content_list) == 1, "got one TextContent item from search")
        payload = json.loads(content_list[0].text)
        _assert(payload.get("success") is True, f"search success=true (payload: {payload})")

        results = payload["meta"]["results"]
        _assert(len(results) > 0, f"at least one search result returned (got {results})")

        top_path = results[0]["path"]
        _assert(
            "quarto" in top_path.lower(),
            f"top result is the quarto file (got: {top_path})",
        )
        print(f"  top result: {top_path}")
        print(f"  snippet: {results[0]['snippet']}")

    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(run_tests())
