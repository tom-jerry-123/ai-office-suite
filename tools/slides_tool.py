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
@click.option("--input", "input_file", required=True, help="Path to .qmd file")
@click.option("--format", "fmt", required=True, type=click.Choice(["revealjs", "pdf", "pptx"]))
@click.option("--output-dir", default=None, help="Output directory (default: same as input)")
def render(input_file, fmt, output_dir):
    src = Path(input_file).resolve()
    if not src.exists():
        emit({"success": False, "error": f"Input file not found: {src}", "stderr": ""}, 1)

    cmd = ["quarto", "render", str(src), "--to", fmt]
    if output_dir:
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd += ["--output-dir", str(out_dir)]
    else:
        out_dir = src.parent

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        emit({"success": False, "error": "Render failed", "stderr": result.stderr}, 1)

    ext = {"revealjs": ".html", "pdf": ".pdf", "pptx": ".pptx"}[fmt]
    output_path = out_dir / (src.stem + ext)

    if not output_path.exists():
        emit({"success": False, "error": f"Expected output not found: {output_path}", "stderr": result.stderr}, 1)

    emit({
        "success": True,
        "output": str(output_path),
        "meta": {"format": fmt, "size_bytes": output_path.stat().st_size}
    })


if __name__ == "__main__":
    cli()
