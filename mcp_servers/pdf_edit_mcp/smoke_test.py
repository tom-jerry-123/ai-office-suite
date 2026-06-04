"""
Smoke test for the pdf-edit-mcp server.

Tests:
  1. Tool list includes all five pdf-edit tools.
  2. pdf_merge: merge two copies of article.pdf → non-empty 2-page PDF.
  3. pdf_split: split the merged PDF at page 1 → two single-page PDFs.
  4. pdf_page_to_image: render page 1 of article.pdf → non-empty PNG.

Split range "1,2" produces two single-page PDFs from the 2-page merged file.
"""

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Add mcp_servers/ to sys.path so "pdf_edit_mcp.server" resolves without
# shadowing the installed "mcp" SDK (same pattern as latex_mcp smoke test).
_MCP_SERVERS_DIR = str(_REPO_ROOT / "mcp_servers")
if _MCP_SERVERS_DIR not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_DIR)

from pdf_edit_mcp.server import mcp, pdf_merge, pdf_split, pdf_page_to_image  # noqa: E402

_WORKSPACE = _REPO_ROOT / "workspace"
_ARTICLE = str(_WORKSPACE / "article.pdf")

# ── helpers ─────────────────────────────────────────────────────────────────

def _assert_success(raw: str, label: str) -> dict:
    result = json.loads(raw)
    assert result.get("success") is True, (
        f"[{label}] FAILED: {result.get('error')} | stderr: {result.get('stderr', '')[:300]}"
    )
    return result


def _assert_nonempty_file(path: str, label: str):
    p = Path(path)
    assert p.exists(), f"[{label}] output file missing: {path}"
    size = p.stat().st_size
    assert size > 0, f"[{label}] output file is empty: {path}"
    return size

# ── test 1: tool list ────────────────────────────────────────────────────────

def test_tool_list():
    tools = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {"pdf_merge", "pdf_split", "pdf_rotate", "pdf_compress", "pdf_page_to_image"}
    missing = expected - tools
    assert not missing, f"Missing tools: {missing} (found: {tools})"
    print(f"  tools: {sorted(tools)}  OK")

# ── test 2: pdf_merge ────────────────────────────────────────────────────────

def test_merge() -> str:
    """Merge article.pdf with itself → 2-page PDF. Returns output path."""
    out = str(_WORKSPACE / "smoke_merge.pdf")
    raw = pdf_merge(inputs=[_ARTICLE, _ARTICLE], output=out)
    result = _assert_success(raw, "pdf_merge")
    size = _assert_nonempty_file(result["output"], "pdf_merge")
    pages = result["meta"]["pages"]
    assert pages == 2, f"Expected 2 pages after merge, got {pages}"
    print(f"  output: {result['output']}  ({size} bytes, {pages} pages)  OK")
    return result["output"]

# ── test 3: pdf_split ────────────────────────────────────────────────────────

def test_split(merged_pdf: str):
    """Split the merged 2-page PDF into two single-page PDFs."""
    out_dir = str(_WORKSPACE / "smoke_split")
    raw = pdf_split(input=merged_pdf, ranges="1,2", output_dir=out_dir)
    result = _assert_success(raw, "pdf_split")
    files = result["meta"]["files"]
    assert len(files) == 2, f"Expected 2 split files, got {len(files)}: {files}"
    for f in files:
        size = _assert_nonempty_file(f, "pdf_split")
        print(f"  part: {f}  ({size} bytes)  OK")

# ── test 4: pdf_page_to_image ────────────────────────────────────────────────

def test_page_to_image():
    out = str(_WORKSPACE / "smoke_page1.png")
    raw = pdf_page_to_image(input=_ARTICLE, page=1, output=out, dpi=72)
    result = _assert_success(raw, "pdf_page_to_image")
    size = _assert_nonempty_file(result["output"], "pdf_page_to_image")
    meta = result["meta"]
    assert meta["width_px"] > 0 and meta["height_px"] > 0
    print(f"  output: {result['output']}  ({size} bytes, "
          f"{meta['width_px']}x{meta['height_px']} px)  OK")

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== pdf-edit-mcp smoke test ===")

    print("[1] tool list")
    test_tool_list()

    print("[2] pdf_merge")
    merged = test_merge()

    print("[3] pdf_split")
    test_split(merged)

    print("[4] pdf_page_to_image")
    test_page_to_image()

    print("=== all tests passed ===")


if __name__ == "__main__":
    main()
