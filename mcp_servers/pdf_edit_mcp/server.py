"""
PDF-edit MCP server — stdio transport.

Exposes tools:
  pdf_merge(inputs, output)
  pdf_split(input, ranges, output_dir)
  pdf_rotate(input, degrees, output[, pages])
  pdf_compress(input, output)
  pdf_page_to_image(input, page, output[, dpi])

Delegates to tools/pdf_tool.py via subprocess and returns its JSON contract
verbatim as MCP TextContent:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}

All output paths must be under workspace/. python and env PATH are derived
from sys.executable — no hardcoded personal paths.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from mcp.server import FastMCP

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTHON = sys.executable
_CONDA_BIN = os.path.dirname(sys.executable)
_PDF_TOOL = str(_REPO_ROOT / "tools" / "pdf_tool.py")
_DEFAULT_OUTPUT_DIR = str(_REPO_ROOT / "workspace")

# Inject conda env bin so subprocesses find PyMuPDF-dependent tools correctly.
_SUBPROCESS_ENV = {**os.environ, "PATH": f"{_CONDA_BIN}:/usr/bin:/bin"}

mcp = FastMCP("pdf-edit-mcp")


def _run(args: list[str]) -> str:
    """Run pdf_tool.py with the given args; return JSON result string."""
    cmd = [_PYTHON, _PDF_TOOL] + args
    result = subprocess.run(cmd, capture_output=True, text=True, env=_SUBPROCESS_ENV)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "success": False,
            "error": "pdf_tool.py returned non-JSON output",
            "stderr": result.stderr,
        }
    return json.dumps(payload)


@mcp.tool()
def pdf_merge(inputs: list[str], output: str) -> str:
    """Merge two or more PDF files into one.

    Args:
        inputs: List of input PDF paths (in merge order).
        output: Output PDF path. Should be under workspace/.

    Returns:
        JSON contract: success → output path + page count; failure → error + stderr.
    """
    args = ["pdf-merge"]
    for inp in inputs:
        args += ["--input", inp]
    args += ["--output", output]
    return _run(args)


@mcp.tool()
def pdf_split(input: str, ranges: str, output_dir: str) -> str:
    """Split a PDF by page ranges; each range produces a separate output PDF.

    Args:
        input: Source PDF path.
        ranges: Comma-separated page ranges (1-based), e.g. "1-3,5,7-9".
            Each token becomes one output file.
        output_dir: Directory for split PDFs. Should be under workspace/.

    Returns:
        JSON contract: success → first output path (or output_dir) + files list;
        failure → error + stderr.
    """
    return _run(["pdf-split", "--input", input, "--ranges", ranges, "--output-dir", output_dir])


@mcp.tool()
def pdf_rotate(
    input: str,
    degrees: Literal["90", "180", "270"],
    output: str,
    pages: str | None = None,
) -> str:
    """Rotate pages in a PDF clockwise by 90, 180, or 270 degrees.

    Args:
        input: Source PDF path.
        degrees: Clockwise rotation — "90", "180", or "270".
        output: Output PDF path. Should be under workspace/.
        pages: Optional comma-separated 1-based page numbers to rotate,
            e.g. "1,3". Omit to rotate all pages.

    Returns:
        JSON contract: success → output path + rotation metadata; failure → error + stderr.
    """
    args = ["pdf-rotate", "--input", input, "--degrees", degrees, "--output", output]
    if pages:
        args += ["--pages", pages]
    return _run(args)


@mcp.tool()
def pdf_compress(input: str, output: str) -> str:
    """Re-save a PDF with deflate compression and garbage collection to reduce file size.

    Uses PyMuPDF (pikepdf would give stronger compression but is not installed).

    Args:
        input: Source PDF path.
        output: Output PDF path. Should be under workspace/.

    Returns:
        JSON contract: success → output path + size comparison; failure → error + stderr.
    """
    return _run(["pdf-compress", "--input", input, "--output", output])


@mcp.tool()
def pdf_page_to_image(
    input: str,
    page: int,
    output: str,
    dpi: int = 150,
) -> str:
    """Render a single PDF page to a raster image for visual inspection.

    Args:
        input: Source PDF path.
        page: 1-based page number to render.
        output: Output image path (.png or .jpg). Should be under workspace/.
        dpi: Render resolution (default 150). Higher values produce larger, sharper images.

    Returns:
        JSON contract: success → output path + image dimensions; failure → error + stderr.
    """
    return _run([
        "pdf-page-to-image",
        "--input", input,
        "--page", str(page),
        "--output", output,
        "--dpi", str(dpi),
    ])


if __name__ == "__main__":
    mcp.run(transport="stdio")
