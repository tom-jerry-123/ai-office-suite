#!/usr/bin/env python3
"""PDF editing CLI backed by PyMuPDF.

All commands exit 0 on success and 1 on failure. stdout is always valid JSON:
  {"success": true,  "output": "<path>", "meta": {...}}
  {"success": false, "error": "<msg>",  "stderr": "<raw>"}
"""
import json
import sys
from pathlib import Path

import click
import fitz  # PyMuPDF


def emit(data: dict, exit_code: int = 0):
    print(json.dumps(data))
    sys.exit(exit_code)


def _open(path: str, label: str = "Input") -> fitz.Document:
    """Open a PDF; emit failure and exit if the file is missing or unreadable."""
    p = Path(path).resolve()
    if not p.exists():
        emit({"success": False, "error": f"{label} file not found: {p}", "stderr": ""}, 1)
    try:
        return fitz.open(str(p))
    except Exception as exc:
        emit({"success": False, "error": f"Cannot open {p}: {exc}", "stderr": ""}, 1)


def _ensure_dir(path: str) -> Path:
    d = Path(path).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


@click.group()
def cli():
    pass


# ---------------------------------------------------------------------------
# pdf_merge
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "inputs", required=True, multiple=True,
              help="Input PDF paths (repeat for each file, in order).")
@click.option("--output", required=True, help="Output PDF path.")
def pdf_merge(inputs, output):
    """Merge two or more PDFs into one."""
    if len(inputs) < 2:
        emit({"success": False, "error": "At least two --input files are required.", "stderr": ""}, 1)

    out_path = Path(output).resolve()
    _ensure_dir(str(out_path.parent))

    merged = fitz.open()
    for src in inputs:
        doc = _open(src)
        merged.insert_pdf(doc)
        doc.close()

    merged.save(str(out_path), garbage=4, deflate=True)
    merged.close()

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {"pages": fitz.open(str(out_path)).page_count,
                 "size_bytes": out_path.stat().st_size},
    })


# ---------------------------------------------------------------------------
# pdf_split
# ---------------------------------------------------------------------------

def _parse_ranges(ranges_str: str, page_count: int) -> list[list[int]]:
    """Parse a range string like "1-3,5,7-9" into a list of 0-based page lists.

    Each comma-separated token becomes one output file.
    Page numbers in the input are 1-based.
    """
    groups = []
    for token in ranges_str.split(","):
        token = token.strip()
        if "-" in token:
            start, end = token.split("-", 1)
            start, end = int(start), int(end)
            groups.append(list(range(start - 1, end)))  # convert to 0-based
        else:
            groups.append([int(token) - 1])
    return groups


@cli.command()
@click.option("--input", "input_file", required=True, help="Source PDF path.")
@click.option("--ranges", required=True,
              help='Page ranges to extract, e.g. "1-3,5" produces two files.')
@click.option("--output-dir", required=True, help="Directory for split output PDFs.")
def pdf_split(input_file, ranges, output_dir):
    """Split a PDF by page ranges; each range becomes a separate PDF."""
    src = _open(input_file)
    out_dir = _ensure_dir(output_dir)
    stem = Path(input_file).stem

    try:
        groups = _parse_ranges(ranges, src.page_count)
    except Exception as exc:
        emit({"success": False, "error": f"Invalid ranges '{ranges}': {exc}", "stderr": ""}, 1)

    outputs = []
    for i, pages in enumerate(groups):
        part = fitz.open()
        part.insert_pdf(src, from_page=pages[0], to_page=pages[-1])
        out_path = out_dir / f"{stem}_part{i + 1}.pdf"
        part.save(str(out_path), garbage=4, deflate=True)
        part.close()
        outputs.append(str(out_path))

    src.close()
    emit({
        "success": True,
        "output": outputs[0] if len(outputs) == 1 else str(out_dir),
        "meta": {"parts": len(outputs), "files": outputs},
    })


# ---------------------------------------------------------------------------
# pdf_rotate
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source PDF path.")
@click.option("--degrees", required=True, type=click.Choice(["90", "180", "270"]),
              help="Clockwise rotation in degrees.")
@click.option("--output", required=True, help="Output PDF path.")
@click.option("--pages", default=None,
              help='1-based page numbers to rotate, e.g. "1,3". Omit to rotate all.')
def pdf_rotate(input_file, degrees, output, pages):
    """Rotate pages in a PDF by 90, 180, or 270 degrees clockwise."""
    src = _open(input_file)
    out_path = Path(output).resolve()
    _ensure_dir(str(out_path.parent))

    deg = int(degrees)

    if pages:
        try:
            page_nums = [int(p.strip()) - 1 for p in pages.split(",")]
        except ValueError as exc:
            emit({"success": False, "error": f"Invalid pages '{pages}': {exc}", "stderr": ""}, 1)
    else:
        page_nums = list(range(src.page_count))

    for idx in page_nums:
        if 0 <= idx < src.page_count:
            page = src[idx]
            page.set_rotation((page.rotation + deg) % 360)

    src.save(str(out_path), garbage=4, deflate=True)
    src.close()

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {"degrees": deg, "pages_rotated": len(page_nums),
                 "size_bytes": out_path.stat().st_size},
    })


# ---------------------------------------------------------------------------
# pdf_compress
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source PDF path.")
@click.option("--output", required=True, help="Output PDF path.")
def pdf_compress(input_file, output):
    """Re-save a PDF with deflate compression and garbage collection.

    Uses PyMuPDF (pikepdf would give better results but is not installed).
    """
    src = _open(input_file)
    out_path = Path(output).resolve()
    _ensure_dir(str(out_path.parent))

    src.save(str(out_path), garbage=4, deflate=True, clean=True)
    src.close()

    original_size = Path(input_file).resolve().stat().st_size
    compressed_size = out_path.stat().st_size

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "original_bytes": original_size,
            "compressed_bytes": compressed_size,
            "ratio": round(compressed_size / original_size, 3) if original_size else None,
        },
    })


# ---------------------------------------------------------------------------
# pdf_page_to_image
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--input", "input_file", required=True, help="Source PDF path.")
@click.option("--page", required=True, type=int, help="1-based page number to render.")
@click.option("--output", required=True, help="Output image path (.png or .jpg).")
@click.option("--dpi", default=150, type=int, show_default=True, help="Render resolution.")
def pdf_page_to_image(input_file, page, output, dpi):
    """Render a single PDF page to a raster image (PNG/JPEG)."""
    src = _open(input_file)
    page_idx = page - 1  # convert to 0-based

    if not (0 <= page_idx < src.page_count):
        emit({
            "success": False,
            "error": f"Page {page} out of range (document has {src.page_count} pages).",
            "stderr": "",
        }, 1)

    out_path = Path(output).resolve()
    _ensure_dir(str(out_path.parent))

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = src[page_idx].get_pixmap(matrix=mat, alpha=False)

    suffix = out_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        pix.save(str(out_path), output="jpeg")
    else:
        pix.save(str(out_path))  # default PNG

    src.close()

    emit({
        "success": True,
        "output": str(out_path),
        "meta": {
            "page": page,
            "dpi": dpi,
            "width_px": pix.width,
            "height_px": pix.height,
            "size_bytes": out_path.stat().st_size,
        },
    })


if __name__ == "__main__":
    cli()
