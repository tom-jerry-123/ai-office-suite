"""
LaTeX MCP server — stdio transport.

Exposes a single tool:
  latex_compile(input, output_dir=None, engine="tectonic")

Delegates to tools/latex_tool.py via subprocess and returns its JSON
contract verbatim as MCP TextContent:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}

Default output_dir is workspace/ (repo root) so compiled PDFs never land
inside templates/ or other source directories.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from mcp.server import FastMCP

# Absolute paths so the server works regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
# Derive python and its bin dir from the running interpreter — no hardcoded user paths.
_PYTHON = sys.executable
_CONDA_BIN = os.path.dirname(sys.executable)
_LATEX_TOOL = str(_REPO_ROOT / "tools" / "latex_tool.py")
_DEFAULT_OUTPUT_DIR = str(_REPO_ROOT / "workspace")

# Subprocess environment: inject the conda env bin so tectonic/pdflatex are found
# even when the shell PATH is missing or unexpanded (known environment issue).
_SUBPROCESS_ENV = {**os.environ, "PATH": f"{_CONDA_BIN}:/usr/bin:/bin"}

mcp = FastMCP("latex-mcp")


@mcp.tool()
def latex_compile(
    input: str,
    output_dir: str | None = None,
    engine: Literal["tectonic", "pdflatex"] = "tectonic",
) -> str:
    """Compile a .tex file to PDF using the specified engine.

    Args:
        input: Path to the .tex source file.
        output_dir: Directory for the output PDF. Defaults to workspace/ in the
            repo root (never the source directory) so templates stay clean.
        engine: LaTeX engine — "tectonic" (default, auto-downloads packages) or
            "pdflatex".

    Returns:
        JSON string matching the tool contract:
          success -> {"success": true, "output": "<pdf_path>", "meta": {...}}
          failure -> {"success": false, "error": "<msg>", "stderr": "<raw>"}
    """
    out_dir = output_dir if output_dir is not None else _DEFAULT_OUTPUT_DIR

    cmd = [
        _PYTHON, _LATEX_TOOL, "compile",
        "--input", input,
        "--output-dir", out_dir,
        "--engine", engine,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=_SUBPROCESS_ENV)

    # latex_tool.py always emits valid JSON on stdout (exit 0 or 1).
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "success": False,
            "error": "latex_tool.py returned non-JSON output",
            "stderr": result.stderr,
        }

    return json.dumps(payload)


if __name__ == "__main__":
    mcp.run(transport="stdio")
