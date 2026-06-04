#!/usr/bin/env python3
"""Smoke test for quarto-mcp server.

Tests:
  1. Server module imports without error.
  2. list_tools() returns all three expected tools.
  3. quarto_render on templates/quarto/slides.qmd -> revealjs succeeds
     and produces a non-empty output file.
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path so relative imports work when run directly
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


def _assert(condition: bool, msg: str):
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


async def run_tests():
    # ------------------------------------------------------------------
    # Test 1: import
    # ------------------------------------------------------------------
    print("Test 1: import server module")
    # Use importlib to avoid collision with the installed `mcp` SDK package
    # (our local mcp/ directory is not a Python package, just a filesystem dir)
    import importlib.util
    _server_path = Path(__file__).resolve().parent / "server.py"
    spec = importlib.util.spec_from_file_location("quarto_mcp_server", _server_path)
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    srv = server_mod.server
    print("  ok: server module imported")

    # ------------------------------------------------------------------
    # Test 2: list_tools returns expected tools
    # ------------------------------------------------------------------
    print("Test 2: list_tools")
    # The list_tools handler is registered via decorator; call it directly
    # by invoking the underlying handler registered on the server.
    from mcp import types

    # Retrieve registered handler for ListToolsRequest
    handler = srv.request_handlers.get(types.ListToolsRequest)
    _assert(handler is not None, "ListToolsRequest handler registered")

    result = await handler(types.ListToolsRequest(method="tools/list", params=None))
    # result is a ListToolsResult
    tool_names = {t.name for t in result.root.tools}
    expected = {"quarto_render", "quarto_create", "quarto_check"}
    _assert(
        expected == tool_names,
        f"tools listed correctly (got {tool_names})",
    )

    # ------------------------------------------------------------------
    # Test 3: quarto_render on slides.qmd -> revealjs
    # ------------------------------------------------------------------
    print("Test 3: quarto_render (revealjs)")
    slides_qmd = _REPO_ROOT / "templates" / "quarto" / "slides.qmd"
    output_dir = _REPO_ROOT / "workspace" / "smoke_test_out"

    _assert(slides_qmd.exists(), f"template exists at {slides_qmd}")

    content_list = await server_mod._quarto_render({
        "input": str(slides_qmd),
        "format": "revealjs",
        "output_dir": str(output_dir),
    })

    _assert(len(content_list) == 1, "got one TextContent item")
    payload = json.loads(content_list[0].text)

    _assert(payload.get("success") is True, f"success=true (payload: {payload})")

    out_path = Path(payload["output"])
    _assert(out_path.exists(), f"output file exists: {out_path}")
    _assert(out_path.stat().st_size > 0, f"output file non-empty ({out_path.stat().st_size} bytes)")
    print(f"  output: {out_path} ({out_path.stat().st_size} bytes)")

    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(run_tests())
