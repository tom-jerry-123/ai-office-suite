"""
Image-tools MCP server — stdio transport.

Exposes tools:
  image_convert(input, output, format[, quality])
  image_resize(input, output[, width, height, fit])
  image_optimize(input, output[, max_kb, quality])
  image_strip_exif(input, output)
  image_metadata(input)

Delegates to tools/image_tool.py via subprocess and returns its JSON contract
verbatim as MCP TextContent:
  success: {"success": true, "output": "<path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}

All output paths should be under workspace/. Python and env PATH are derived
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
_IMAGE_TOOL = str(_REPO_ROOT / "tools" / "image_tool.py")

# Inject conda env bin so Pillow and other env packages resolve correctly.
_SUBPROCESS_ENV = {**os.environ, "PATH": f"{_CONDA_BIN}:/usr/bin:/bin"}

mcp = FastMCP("image-mcp")


def _run(args: list[str]) -> str:
    """Run image_tool.py with the given args; return JSON result string."""
    cmd = [_PYTHON, _IMAGE_TOOL] + args
    result = subprocess.run(cmd, capture_output=True, text=True, env=_SUBPROCESS_ENV)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "success": False,
            "error": "image_tool.py returned non-JSON output",
            "stderr": result.stderr,
        }
    return json.dumps(payload)


@mcp.tool()
def image_convert(
    input: str,
    output: str,
    format: Literal["PNG", "JPEG", "WEBP", "GIF", "TIFF"],
    quality: int | None = None,
) -> str:
    """Convert an image to a different format.

    Args:
        input: Source image path.
        output: Output image path. Should be under workspace/.
        format: Target format — PNG, JPEG, WEBP, GIF, or TIFF.
        quality: Quality for lossy formats JPEG/WEBP (1–95). Ignored for PNG/TIFF.
            Alpha-channel images converted to JPEG are flattened onto a white background.

    Returns:
        JSON contract: success → output path + format/dimensions; failure → error + stderr.
    """
    args = ["image-convert", "--input", input, "--output", output, "--format", format]
    if quality is not None:
        args += ["--quality", str(quality)]
    return _run(args)


@mcp.tool()
def image_resize(
    input: str,
    output: str,
    width: int | None = None,
    height: int | None = None,
    fit: Literal["contain", "cover", "fill"] = "contain",
) -> str:
    """Resize an image with configurable fit mode.

    Args:
        input: Source image path.
        output: Output image path. Should be under workspace/.
        width: Target width in pixels. Omit to derive from height + aspect ratio.
        height: Target height in pixels. Omit to derive from width + aspect ratio.
        fit: How to fit the image into the target box:
            contain (default) — fit within the box preserving aspect ratio (may be smaller on one axis);
            cover — crop to fill exactly, preserving aspect ratio;
            fill — stretch to exact dimensions (may distort).

    Returns:
        JSON contract: success → output path + final dimensions; failure → error + stderr.
    """
    args = ["image-resize", "--input", input, "--output", output, "--fit", fit]
    if width is not None:
        args += ["--width", str(width)]
    if height is not None:
        args += ["--height", str(height)]
    return _run(args)


@mcp.tool()
def image_optimize(
    input: str,
    output: str,
    max_kb: int | None = None,
    quality: int = 85,
) -> str:
    """Re-encode an image to reduce file size, optionally targeting a max KB budget.

    Alpha-aware: images with transparency are encoded as WebP (lossy, preserves alpha).
    Alpha-free PNGs are converted to JPEG for smaller size. Other formats keep their format.
    Quality is reduced iteratively (in steps of 5) until the output fits max_kb.

    Args:
        input: Source image path.
        output: Output image path. Should be under workspace/.
        max_kb: Optional target maximum file size in KB. Quality is reduced until the file fits.
        quality: Starting quality for lossy encoding (1–95, default 85).

    Returns:
        JSON contract: success → output path + format/quality used/size comparison;
        failure → error + stderr.
    """
    args = ["image-optimize", "--input", input, "--output", output, "--quality", str(quality)]
    if max_kb is not None:
        args += ["--max-kb", str(max_kb)]
    return _run(args)


@mcp.tool()
def image_strip_exif(input: str, output: str) -> str:
    """Strip EXIF and other metadata from an image, preserving pixel data only.

    Args:
        input: Source image path.
        output: Output image path. Should be under workspace/.

    Returns:
        JSON contract: success → output path + format/size; failure → error + stderr.
    """
    return _run(["image-strip-exif", "--input", input, "--output", output])


@mcp.tool()
def image_metadata(input: str) -> str:
    """Read image dimensions, format, mode, EXIF presence, and file size.

    No output file is written — the result is returned as JSON metadata.

    Args:
        input: Image path to inspect.

    Returns:
        JSON contract: success → output=input path, meta={width, height, format, mode,
        has_exif, file_size_bytes}; failure → error + stderr.
    """
    return _run(["image-metadata", "--input", input])


if __name__ == "__main__":
    mcp.run(transport="stdio")
