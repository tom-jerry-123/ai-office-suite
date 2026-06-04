#!/usr/bin/env python3
"""Image processing CLI backed by Pillow.

All commands exit 0 on success and 1 on failure. stdout is always valid JSON:
  {"success": true,  "output": "<path>", "meta": {...}}
  {"success": false, "error": "<msg>",  "stderr": "<raw>"}
"""
import io
import json
import sys
from pathlib import Path

import click
from PIL import Image, ImageOps


def emit(data: dict, exit_code: int = 0):
    print(json.dumps(data))
    sys.exit(exit_code)


def _open(path: str, label: str = "Input") -> Image.Image:
    """Open an image; emit failure and exit if missing or unreadable."""
    p = Path(path).resolve()
    if not p.exists():
        emit({"success": False, "error": f"{label} file not found: {p}", "stderr": ""}, 1)
    try:
        img = Image.open(str(p))
        img.load()  # force decode so errors surface here
        return img
    except Exception as exc:
        emit({"success": False, "error": f"Cannot open {p}: {exc}", "stderr": ""}, 1)


def _ensure_dir(path: str) -> Path:
    d = Path(path).resolve().parent
    d.mkdir(parents=True, exist_ok=True)
    return Path(path).resolve()


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and img.info.get("transparency") is not None
    )


def _save_kwargs(fmt: str, quality: int | None) -> dict:
    kwargs: dict = {}
    if fmt in ("JPEG", "WEBP") and quality is not None:
        kwargs["quality"] = quality
    if fmt == "PNG":
        kwargs["optimize"] = True
    return kwargs


@click.group()
def cli():
    pass


# ---------------------------------------------------------------------------
# image_convert
# ---------------------------------------------------------------------------

_FORMATS = click.Choice(["PNG", "JPEG", "WEBP", "GIF", "TIFF"], case_sensitive=False)


@cli.command()
@click.option("--input", "input_file", required=True, help="Source image path.")
@click.option("--output", required=True, help="Output image path.")
@click.option("--format", "fmt", required=True, type=_FORMATS, help="Target format.")
@click.option("--quality", default=None, type=click.IntRange(1, 95),
              help="Quality for JPEG/WEBP (1–95). Ignored for lossless formats.")
def image_convert(input_file, output, fmt, quality):
    """Convert an image to a different format."""
    img = _open(input_file)
    out_path = _ensure_dir(output)
    fmt = fmt.upper()

    # JPEG cannot carry alpha — flatten onto white before converting.
    if fmt == "JPEG" and _has_alpha(img):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
        img = bg
    elif fmt not in ("PNG", "WEBP", "GIF", "TIFF"):
        img = img.convert("RGB")
    else:
        # PNG/WEBP/TIFF handle RGBA natively; GIF needs palette
        if fmt == "GIF" and img.mode not in ("P", "L"):
            img = img.convert("P")

    img.save(str(out_path), format=fmt, **_save_kwargs(fmt, quality))

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "format": fmt,
            "width": img.width,
            "height": img.height,
            "size_bytes": out_path.stat().st_size,
        },
    })


# ---------------------------------------------------------------------------
# image_resize
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source image path.")
@click.option("--output", required=True, help="Output image path.")
@click.option("--width", default=None, type=int, help="Target width in pixels.")
@click.option("--height", default=None, type=int, help="Target height in pixels.")
@click.option("--fit", default="contain",
              type=click.Choice(["contain", "cover", "fill"]),
              help="contain: fit within box (default). cover: crop to fill. fill: stretch.")
def image_resize(input_file, output, width, height, fit):
    """Resize an image with configurable fit mode."""
    if width is None and height is None:
        emit({"success": False,
              "error": "At least one of --width or --height is required.", "stderr": ""}, 1)

    img = _open(input_file)
    out_path = _ensure_dir(output)

    orig_w, orig_h = img.size

    # Derive missing dimension maintaining aspect ratio.
    if width is None:
        width = max(1, round(orig_w * height / orig_h))
    if height is None:
        height = max(1, round(orig_h * width / orig_w))

    box = (width, height)

    if fit == "contain":
        # Fit within the box; may leave space on one axis (no padding added).
        img.thumbnail(box, Image.Resampling.LANCZOS)
        result = img
    elif fit == "cover":
        # Crop to exactly fill the box while preserving aspect ratio.
        result = ImageOps.fit(img, box, Image.Resampling.LANCZOS)
    else:  # fill
        result = img.resize(box, Image.Resampling.LANCZOS)

    # Infer output format from extension.
    ext = out_path.suffix.lstrip(".").upper() or img.format or "PNG"
    if ext == "JPG":
        ext = "JPEG"

    result.save(str(out_path), format=ext)

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "width": result.width,
            "height": result.height,
            "fit": fit,
            "size_bytes": out_path.stat().st_size,
        },
    })


# ---------------------------------------------------------------------------
# image_optimize
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source image path.")
@click.option("--output", required=True, help="Output image path.")
@click.option("--max-kb", default=None, type=int,
              help="Maximum output size in KB. Quality is reduced iteratively to hit target.")
@click.option("--quality", default=85, type=click.IntRange(1, 95), show_default=True,
              help="Starting quality for lossy encode (1–95).")
def image_optimize(input_file, output, max_kb, quality):
    """Re-encode an image to reduce file size, optionally targeting a max KB budget.

    Alpha-aware: images with transparency are encoded as WebP (preserves alpha).
    Alpha-free images are encoded as JPEG when the source is PNG (lossy but smaller);
    other formats keep their original format.
    """
    img = _open(input_file)
    out_path = _ensure_dir(output)
    src_path = Path(input_file).resolve()

    src_fmt = (img.format or src_path.suffix.lstrip(".")).upper()
    if src_fmt == "JPG":
        src_fmt = "JPEG"

    # Decide output format and prepare working image:
    # - alpha present → WebP (lossy, preserves alpha)
    # - PNG with no alpha → JPEG (better compression than PNG lossless)
    # - anything else → keep original format (or JPEG as fallback)
    if _has_alpha(img):
        out_fmt = "WEBP"
        work_img = img.convert("RGBA")
    elif src_fmt == "PNG":
        out_fmt = "JPEG"
        work_img = img.convert("RGB")
    else:
        out_fmt = src_fmt if src_fmt in ("JPEG", "WEBP") else "JPEG"
        work_img = img.convert("RGB") if out_fmt == "JPEG" and img.mode != "RGB" else img

    max_bytes = max_kb * 1024 if max_kb else None
    q = quality

    while True:
        buf = io.BytesIO()
        save_kw: dict = {"format": out_fmt}
        if out_fmt in ("JPEG", "WEBP"):
            save_kw["quality"] = q
        if out_fmt == "PNG":
            save_kw["optimize"] = True
        work_img.save(buf, **save_kw)
        size = buf.tell()

        if max_bytes is None or size <= max_bytes or q <= 10:
            break
        q -= 5

    out_path.write_bytes(buf.getvalue())

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "format": out_fmt,
            "quality_used": q,
            "size_bytes": out_path.stat().st_size,
            "original_bytes": src_path.stat().st_size,
        },
    })


# ---------------------------------------------------------------------------
# image_strip_exif
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source image path.")
@click.option("--output", required=True, help="Output image path.")
def image_strip_exif(input_file, output):
    """Strip EXIF and other metadata from an image."""
    img = _open(input_file)
    out_path = _ensure_dir(output)

    src_fmt = (img.format or out_path.suffix.lstrip(".")).upper()
    if src_fmt == "JPG":
        src_fmt = "JPEG"

    # Re-create image data without any metadata by copying pixel data only.
    clean = Image.frombytes(img.mode, img.size, img.tobytes())

    save_kw: dict = {"format": src_fmt}
    if src_fmt in ("JPEG", "WEBP"):
        save_kw["exif"] = b""
    clean.save(str(out_path), **save_kw)

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "format": src_fmt,
            "size_bytes": out_path.stat().st_size,
        },
    })


# ---------------------------------------------------------------------------
# image_metadata
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Image path to inspect.")
def image_metadata(input_file):
    """Read image dimensions, format, mode, and EXIF presence."""
    p = Path(input_file).resolve()
    if not p.exists():
        emit({"success": False, "error": f"File not found: {p}", "stderr": ""}, 1)

    try:
        img = Image.open(str(p))
        img.load()
    except Exception as exc:
        emit({"success": False, "error": f"Cannot open {p}: {exc}", "stderr": ""}, 1)

    has_exif = bool(img.info.get("exif"))
    if not has_exif and hasattr(img, "_getexif"):
        try:
            has_exif = bool(img._getexif())
        except Exception:
            pass

    emit({
        "success": True,
        "output": str(p),   # no output file; output = input for metadata queries
        "meta": {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "has_exif": has_exif,
            "file_size_bytes": p.stat().st_size,
        },
    })


if __name__ == "__main__":
    cli()
