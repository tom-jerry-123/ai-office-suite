#!/usr/bin/env python3
"""Smoke test for docx-mcp server.

Tests:
  1. Server module imports without error.
  2. list_tools() returns both expected tools.
  3. docx_from_markdown converts a small markdown file to .docx,
     asserts success, non-empty output, and valid OOXML zip (PK magic bytes).
  4. docx_to_markdown round-trips the .docx back to markdown,
     asserts success and non-empty output.
"""

import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

_SAMPLE_MD = """\
# Hello from docx-mcp

This is a **test** document with some _italic_ text.

## Section Two

- Item one
- Item two
- Item three

Paragraph with `inline code` and a [link](https://example.com).
"""


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
        "docx_mcp_server",
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
    expected = {"docx_from_markdown", "docx_to_markdown"}
    _assert(expected == tool_names, f"tools listed correctly (got {tool_names})")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        md_file = tmp / "test.md"
        docx_file = tmp / "output" / "test.docx"   # subdir — tests mkdir
        md_file.write_text(_SAMPLE_MD, encoding="utf-8")

        # ------------------------------------------------------------------
        # Test 3: docx_from_markdown
        # ------------------------------------------------------------------
        print("Test 3: docx_from_markdown")
        content_list = server_mod._handle_from_markdown({
            "input": str(md_file),
            "output": str(docx_file),
        })

        _assert(len(content_list) == 1, "got one TextContent item")
        payload = json.loads(content_list[0].text)
        _assert(payload.get("success") is True, f"success=true (payload: {payload})")
        _assert(docx_file.exists(), f"output file exists: {docx_file}")
        _assert(docx_file.stat().st_size > 0, f"output file non-empty ({docx_file.stat().st_size} bytes)")

        # Verify valid OOXML zip: first 4 bytes must be PK\x03\x04
        magic = docx_file.read_bytes()[:4]
        _assert(magic == b"PK\x03\x04", f"valid OOXML zip magic bytes (got {magic!r})")
        print(f"  output: {docx_file} ({docx_file.stat().st_size} bytes), magic: {magic!r}")

        # ------------------------------------------------------------------
        # Test 4: docx_to_markdown (round-trip)
        # ------------------------------------------------------------------
        print("Test 4: docx_to_markdown (round-trip)")
        md_out = tmp / "roundtrip.md"
        content_list = server_mod._handle_to_markdown({
            "input": str(docx_file),
            "output": str(md_out),
        })

        _assert(len(content_list) == 1, "got one TextContent item")
        payload = json.loads(content_list[0].text)
        _assert(payload.get("success") is True, f"success=true (payload: {payload})")
        _assert(md_out.exists(), f"round-trip markdown exists: {md_out}")
        _assert(md_out.stat().st_size > 0, f"round-trip markdown non-empty ({md_out.stat().st_size} bytes)")
        print(f"  round-trip output: {md_out} ({md_out.stat().st_size} bytes)")

    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(run_tests())
