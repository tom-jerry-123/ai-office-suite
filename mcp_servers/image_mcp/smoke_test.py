"""
Smoke test for the image-mcp server.

Tests:
  1. Tool list includes all 5 image tools.
  2. Generate a 400x300 test PNG in workspace/ (no external files needed).
  3. image_convert: PNG → WebP, assert non-empty output.
  4. image_resize: resize to width=200, assert output width=200 and non-empty.
  5. image_optimize: optimize with max_kb=5, assert output ≤ 5120 bytes and non-empty.
  6. image_strip_exif: strip exif, assert success + non-empty output.
  7. image_metadata: read test PNG, assert success + correct dimensions.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Add mcp_servers/ to sys.path so "image_mcp.server" resolves without
# shadowing the installed "mcp" SDK package.
_MCP_SERVERS_DIR = str(_REPO_ROOT / "mcp_servers")
if _MCP_SERVERS_DIR not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_DIR)

from image_mcp.server import (  # noqa: E402
    image_convert,
    image_metadata,
    image_optimize,
    image_resize,
    image_strip_exif,
    mcp,
)

_WORKSPACE = _REPO_ROOT / "workspace"

# ── helpers ──────────────────────────────────────────────────────────────────

def _assert_success(raw: str, label: str) -> dict:
    result = json.loads(raw)
    assert result.get("success") is True, (
        f"[{label}] FAILED: {result.get('error')} | stderr: {result.get('stderr', '')[:300]}"
    )
    return result


def _assert_nonempty_file(path: str, label: str) -> int:
    p = Path(path)
    assert p.exists(), f"[{label}] output file missing: {path}"
    size = p.stat().st_size
    assert size > 0, f"[{label}] output file is empty: {path}"
    return size

# ── test 1: tool list ─────────────────────────────────────────────────────────

def test_tool_list():
    tools = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {"image_convert", "image_resize", "image_optimize",
                "image_strip_exif", "image_metadata"}
    missing = expected - tools
    assert not missing, f"Missing tools: {missing} (found: {tools})"
    print(f"  tools: {sorted(tools)}  OK")

# ── test 2: generate test PNG ─────────────────────────────────────────────────

def make_test_png() -> str:
    """Create a 400x300 RGB PNG with some color variation for realistic compression."""
    out = str(_WORKSPACE / "smoke_test_input.png")
    img = Image.new("RGB", (400, 300), color=(100, 149, 237))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 350, 250], fill=(255, 165, 0))
    draw.ellipse([150, 100, 250, 200], fill=(220, 20, 60))
    img.save(out)
    size = Path(out).stat().st_size
    print(f"  generated test PNG: {out}  ({size} bytes, 400x300)  OK")
    return out

# ── test 3: image_convert ─────────────────────────────────────────────────────

def test_convert(src: str):
    out = str(_WORKSPACE / "smoke_converted.webp")
    raw = image_convert(input=src, output=out, format="WEBP", quality=80)
    result = _assert_success(raw, "image_convert")
    size = _assert_nonempty_file(result["output"], "image_convert")
    assert result["meta"]["format"] == "WEBP"
    print(f"  output: {result['output']}  ({size} bytes)  OK")

# ── test 4: image_resize ──────────────────────────────────────────────────────

def test_resize(src: str):
    out = str(_WORKSPACE / "smoke_resized.png")
    raw = image_resize(input=src, output=out, width=200)
    result = _assert_success(raw, "image_resize")
    size = _assert_nonempty_file(result["output"], "image_resize")
    w = result["meta"]["width"]
    assert w == 200, f"Expected width=200, got {w}"
    print(f"  output: {result['output']}  ({size} bytes, {w}x{result['meta']['height']})  OK")

# ── test 5: image_optimize ────────────────────────────────────────────────────

def test_optimize(src: str):
    out = str(_WORKSPACE / "smoke_optimized.jpg")
    raw = image_optimize(input=src, output=out, max_kb=5)
    result = _assert_success(raw, "image_optimize")
    size = _assert_nonempty_file(result["output"], "image_optimize")
    assert size <= 5120, f"Expected ≤ 5120 bytes, got {size}"
    print(f"  output: {result['output']}  ({size} bytes ≤ 5 KB, "
          f"quality={result['meta']['quality_used']})  OK")

# ── test 6: image_strip_exif ──────────────────────────────────────────────────

def test_strip_exif(src: str):
    out = str(_WORKSPACE / "smoke_stripped.png")
    raw = image_strip_exif(input=src, output=out)
    result = _assert_success(raw, "image_strip_exif")
    size = _assert_nonempty_file(result["output"], "image_strip_exif")
    print(f"  output: {result['output']}  ({size} bytes)  OK")

# ── test 7: image_metadata ────────────────────────────────────────────────────

def test_metadata(src: str):
    raw = image_metadata(input=src)
    result = _assert_success(raw, "image_metadata")
    meta = result["meta"]
    assert meta["width"] == 400, f"Expected width=400, got {meta['width']}"
    assert meta["height"] == 300, f"Expected height=300, got {meta['height']}"
    assert meta["format"] == "PNG"
    print(f"  {meta['width']}x{meta['height']} {meta['format']} mode={meta['mode']} "
          f"has_exif={meta['has_exif']}  OK")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== image-mcp smoke test ===")

    print("[1] tool list")
    test_tool_list()

    print("[2] generate test PNG")
    src = make_test_png()

    print("[3] image_convert (PNG → WebP)")
    test_convert(src)

    print("[4] image_resize (width=200)")
    test_resize(src)

    print("[5] image_optimize (max_kb=5)")
    test_optimize(src)

    print("[6] image_strip_exif")
    test_strip_exif(src)

    print("[7] image_metadata")
    test_metadata(src)

    print("=== all tests passed ===")


if __name__ == "__main__":
    main()
