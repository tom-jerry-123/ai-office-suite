"""
Smoke test for the latex-mcp server.

Tests:
  1. Server imports and tool list includes latex_compile.
  2. latex_compile on templates/latex/article.tex succeeds and produces a
     non-empty PDF under workspace/.
"""

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Add mcp_servers/ (not the repo root) so "latex_mcp.server" resolves cleanly.
_MCP_DIR = str(_REPO_ROOT / "mcp_servers")
if _MCP_DIR not in sys.path:
    sys.path.insert(0, _MCP_DIR)

from latex_mcp.server import latex_compile, mcp  # noqa: E402


def test_tool_list():
    """latex_compile must be registered on the server."""
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert "latex_compile" in tools, f"latex_compile not in tool list: {tools}"
    print(f"  tool list: {tools}  OK")


def test_compile_article():
    """Compile the bundled article template; expect success and a non-empty PDF."""
    tex = str(_REPO_ROOT / "templates" / "latex" / "article.tex")
    workspace = str(_REPO_ROOT / "workspace")

    raw = latex_compile(input=tex, output_dir=workspace, engine="tectonic")
    result = json.loads(raw)

    assert result.get("success") is True, (
        f"Compilation failed: {result.get('error')} | stderr: {result.get('stderr', '')[:500]}"
    )

    pdf_path = Path(result["output"])
    assert pdf_path.exists(), f"PDF not found at: {pdf_path}"
    size = pdf_path.stat().st_size
    assert size > 0, f"PDF is empty: {pdf_path}"

    print(f"  output: {pdf_path}  ({size} bytes)  OK")
    print(f"  meta:   {result.get('meta')}")


def main():
    print("=== latex-mcp smoke test ===")

    print("[1] tool list")
    test_tool_list()

    print("[2] compile templates/latex/article.tex")
    test_compile_article()

    print("=== all tests passed ===")


if __name__ == "__main__":
    main()
