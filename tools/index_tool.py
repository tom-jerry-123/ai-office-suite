#!/usr/bin/env python3
"""Workspace indexing tool — SQLite FTS5 backend.

Commands:
  build [--dir DIR] [--db DB]   Scan DIR, populate DB with documents + FTS5 index.
  search --query Q [--limit N] [--db DB]  FTS5 ranked search, return paths + snippets.

All output is JSON on stdout following the shared contract:
  success: {"success": true, "output": "<db_path>", "meta": {...}}
  failure: {"success": false, "error": "<msg>", "stderr": "<raw>"}
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _REPO_ROOT / "workspace" / "index.db"
_DEFAULT_DIR = _REPO_ROOT / "workspace"

# File extensions we extract text from
_TEXT_EXTS = {".md", ".qmd", ".tex", ".txt"}
_PDF_EXTS = {".pdf"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def emit(data: dict, exit_code: int = 0):
    print(json.dumps(data))
    sys.exit(exit_code)


def _extract_text(path: Path) -> str | None:
    """Return text content for indexable files, or None to skip."""
    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    if ext in _PDF_EXTS:
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
            return "\n".join(parts) if parts else ""
        except Exception:
            return None
    return None  # unsupported type — skip


def _open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            path       TEXT PRIMARY KEY,
            type       TEXT,
            title      TEXT,
            tags       TEXT,
            updated    TEXT,
            char_count INTEGER,
            body       TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(title, body, content=documents, content_rowid=rowid);
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli():
    pass


@cli.command()
@click.option("--dir", "scan_dir", default=None,
              help="Directory to scan (default: workspace/).")
@click.option("--db", "db_path", default=None,
              help="Path to index DB (default: workspace/index.db).")
def build(scan_dir, db_path):
    root = Path(scan_dir).resolve() if scan_dir else _DEFAULT_DIR
    db = Path(db_path).resolve() if db_path else _DEFAULT_DB

    if not root.exists():
        emit({"success": False, "error": f"Directory not found: {root}", "stderr": ""}, 1)

    conn = _open_db(db)
    _init_schema(conn)

    indexed = 0
    skipped = 0

    for fpath in sorted(root.rglob("*")):
        if not fpath.is_file():
            continue
        # Skip the index DB itself
        if fpath.resolve() == db.resolve():
            continue

        body = _extract_text(fpath)
        if body is None:
            skipped += 1
            continue

        ftype = fpath.suffix.lstrip(".") or "txt"
        title = fpath.stem
        updated = datetime.fromtimestamp(fpath.stat().st_mtime).isoformat()
        char_count = len(body)
        abs_path = str(fpath.resolve())

        # Upsert into documents
        conn.execute("""
            INSERT INTO documents (path, type, title, tags, updated, char_count, body)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                type=excluded.type,
                title=excluded.title,
                updated=excluded.updated,
                char_count=excluded.char_count,
                body=excluded.body
        """, (abs_path, ftype, title, updated, char_count, body))

        indexed += 1

    conn.commit()

    # Rebuild the FTS index from the documents table (external-content table
    # does not auto-populate — must be done explicitly after upserts).
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()

    emit({
        "success": True,
        "output": str(db),
        "meta": {"indexed": indexed, "skipped": skipped, "db": str(db)},
    })


@cli.command()
@click.option("--query", required=True, help="FTS5 search query.")
@click.option("--limit", default=10, show_default=True, help="Max results to return.")
@click.option("--db", "db_path", default=None,
              help="Path to index DB (default: workspace/index.db).")
def search(query, limit, db_path):
    db = Path(db_path).resolve() if db_path else _DEFAULT_DB

    if not db.exists():
        emit({"success": False,
              "error": f"Index DB not found: {db}. Run 'build' first.",
              "stderr": ""}, 1)

    conn = _open_db(db)

    try:
        rows = conn.execute("""
            SELECT
                d.path,
                d.title,
                snippet(documents_fts, 1, '[', ']', '...', 16) AS snippet,
                bm25(documents_fts)                             AS rank
            FROM documents_fts
            JOIN documents d ON d.rowid = documents_fts.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        emit({"success": False, "error": f"Search failed: {e}", "stderr": ""}, 1)

    conn.close()

    results = [
        {"path": r["path"], "title": r["title"], "snippet": r["snippet"], "rank": r["rank"]}
        for r in rows
    ]

    emit({
        "success": True,
        "output": str(db),
        "meta": {"results": results, "count": len(results)},
    })


if __name__ == "__main__":
    cli()
