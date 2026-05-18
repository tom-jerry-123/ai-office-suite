#!/usr/bin/env python3
import click
import json
import subprocess
import sys
from pathlib import Path


def emit(data: dict, exit_code: int = 0):
    print(json.dumps(data))
    sys.exit(exit_code)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--input", "input_file", required=True, help="Path to .tex file")
@click.option("--output-dir", default=None, help="Output directory (default: same as input)")
@click.option("--engine", type=click.Choice(["tectonic", "pdflatex"]), default="tectonic")
def compile(input_file, output_dir, engine):
    src = Path(input_file).resolve()
    if not src.exists():
        emit({"success": False, "error": f"Input file not found: {src}", "stderr": ""}, 1)

    out_dir = Path(output_dir).resolve() if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if engine == "tectonic":
        cmd = ["tectonic", "--outdir", str(out_dir), str(src)]
    else:
        cmd = ["pdflatex", f"-output-directory={out_dir}", str(src)]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        emit({"success": False, "error": "Compilation failed", "stderr": result.stderr}, 1)

    pdf_path = out_dir / (src.stem + ".pdf")
    if not pdf_path.exists():
        emit({"success": False, "error": "PDF not produced", "stderr": result.stderr}, 1)

    emit({
        "success": True,
        "output": str(pdf_path),
        "meta": {"engine": engine, "size_bytes": pdf_path.stat().st_size}
    })


if __name__ == "__main__":
    cli()
