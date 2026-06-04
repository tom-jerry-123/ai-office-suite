#!/usr/bin/env python3
"""DOCX export tool — pandoc backend.

Commands:
  from-markdown --input FILE --output FILE [--reference-doc FILE]
      Convert Markdown to .docx via pandoc. Optional --reference-doc for styling.

  to-markdown --input FILE --output FILE
      Convert .docx to Markdown via pandoc (reverse direction).

All output is JSON on stdout following the shared contract:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}
"""

import json
import subprocess
import sys
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def emit(data: dict, exit_code: int = 0):
    print(json.dumps(data))
    sys.exit(exit_code)


def _run_pandoc(cmd: list[str]) -> tuple[int, str, str]:
    """Run a pandoc command; return (returncode, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    pass


@cli.command("from-markdown")
@click.option("--input", "input_file", required=True, help="Path to the Markdown source file.")
@click.option("--output", "output_file", required=True, help="Path for the output .docx file.")
@click.option("--reference-doc", "reference_doc", default=None,
              help="Optional .docx reference document for styling.")
def from_markdown(input_file, output_file, reference_doc):
    src = Path(input_file).resolve()
    out = Path(output_file).resolve()

    if not src.exists():
        emit({"success": False, "error": f"Input file not found: {src}", "stderr": ""}, 1)

    if reference_doc is not None:
        ref = Path(reference_doc).resolve()
        if not ref.exists():
            emit({"success": False,
                  "error": f"Reference doc not found: {ref}", "stderr": ""}, 1)
    else:
        ref = None

    # Ensure output parent directory exists
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["pandoc", str(src), "-o", str(out)]
    if ref is not None:
        cmd += ["--reference-doc", str(ref)]

    rc, _, stderr = _run_pandoc(cmd)
    if rc != 0:
        emit({"success": False, "error": "pandoc failed", "stderr": stderr}, 1)

    if not out.exists():
        emit({"success": False,
              "error": f"Expected output not found: {out}", "stderr": stderr}, 1)

    emit({
        "success": True,
        "output": str(out),
        "meta": {"size_bytes": out.stat().st_size, "format": "docx"},
    })


@cli.command("to-markdown")
@click.option("--input", "input_file", required=True, help="Path to the .docx source file.")
@click.option("--output", "output_file", required=True, help="Path for the output Markdown file.")
def to_markdown(input_file, output_file):
    src = Path(input_file).resolve()
    out = Path(output_file).resolve()

    if not src.exists():
        emit({"success": False, "error": f"Input file not found: {src}", "stderr": ""}, 1)

    # Ensure output parent directory exists
    out.parent.mkdir(parents=True, exist_ok=True)

    rc, _, stderr = _run_pandoc(["pandoc", str(src), "-o", str(out)])
    if rc != 0:
        emit({"success": False, "error": "pandoc failed", "stderr": stderr}, 1)

    if not out.exists():
        emit({"success": False,
              "error": f"Expected output not found: {out}", "stderr": stderr}, 1)

    emit({
        "success": True,
        "output": str(out),
        "meta": {"size_bytes": out.stat().st_size, "format": "markdown"},
    })


if __name__ == "__main__":
    cli()
