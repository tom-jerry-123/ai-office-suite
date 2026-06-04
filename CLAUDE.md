# Office Suite Skills

## Environment

Always activate `conda activate office-suite` before running any tool.
All outputs go to `workspace/`. Never write outside `workspace/` unless explicitly asked.

## Available Tools

### LaTeX

```bash
python tools/latex_tool.py compile --input FILE [--output-dir DIR] [--engine tectonic|pdflatex]
```

- Default engine: `tectonic` (auto-downloads packages, no PATH issues)
- Output: PDF in the same directory as input, or `--output-dir`

### Slides (Quarto)

```bash
python tools/slides_tool.py render --input FILE --format revealjs|pdf|pptx [--output-dir DIR]
```

- Prefer `revealjs` for HTML output (no LaTeX dependency)
- Templates in `templates/quarto/`

## MCP Servers (Horizon 2)

Six local stdio MCP servers are registered in `.mcp.json` (and `config/mcp_servers.json`).
They wrap CLI tools and return the same JSON contract. Restart Claude Code to load them.

### quarto (`mcp_servers/quarto_mcp/server.py`)

- `quarto_render(input, format, output_dir?)` — format ∈ `revealjs|pdf|pptx`. Wraps `slides_tool.py`.
- `quarto_create(template, output_dir)` — copies a `templates/quarto/` template into `workspace/<output_dir>/`.
- `quarto_check()` — runs `quarto check`.

### latex (`mcp_servers/latex_mcp/server.py`)

- `latex_compile(input, output_dir?, engine?)` — engine ∈ `tectonic|pdflatex`. Wraps `latex_tool.py`.
  Defaults `output_dir` to `workspace/` (never the source dir).

### pdf-edit (`mcp_servers/pdf_edit_mcp/server.py`)

- `pdf_merge(inputs[], output)` — concatenate two or more PDFs.
- `pdf_split(input, ranges, output_dir)` — `ranges` like `"1-3,5"`; each token → one output file.
- `pdf_rotate(input, degrees, output, pages?)` — `degrees` ∈ `90|180|270` clockwise.
- `pdf_compress(input, output)` — PyMuPDF deflate/garbage save (pikepdf would compress better but isn't installed).
- `pdf_page_to_image(input, page, output, dpi?)` — render one page to PNG/JPEG for vision inspection.

Wraps `tools/pdf_tool.py` (PyMuPDF).

### index (`mcp_servers/index_mcp/server.py`)

- `index_build(dir?)` — scan `dir` (default `workspace/`), populate `workspace/index.db`
  (SQLite + FTS5). Indexes md/qmd/tex/txt directly, pdf via pdfplumber.
- `index_search(query, limit?)` — FTS5 / bm25 ranked search; returns paths + snippets.

Wraps `tools/index_tool.py`. Use `index_search` to locate workspace files instead of
loading full document text into context.

### image (`mcp_servers/image_mcp/server.py`)

- `image_convert(input, output, format, quality?)` — format ∈ `PNG|JPEG|WEBP|GIF|TIFF`.
- `image_resize(input, output, width?, height?, fit?)` — `fit` ∈ `contain|cover|fill`.
- `image_optimize(input, output, max_kb?, quality?)` — Pillow re-encode; iterates quality to hit
  `max_kb`. Alpha images → WebP (keeps transparency); alpha-free → JPEG.
- `image_strip_exif(input, output)` · `image_metadata(input)`.

Wraps `tools/image_tool.py` (Pillow). External optimizers (oxipng/pngquant) are not installed.

### docx (`mcp_servers/docx_mcp/server.py`)

- `docx_from_markdown(input, output, reference_doc?)` — pandoc md → .docx; `reference_doc` for styling.
- `docx_to_markdown(input, output)` — pandoc .docx → md (read existing docs).

Wraps `tools/docx_tool.py` (pandoc). Export-only; programmatic docx editing is out of scope.

All servers inject the conda-env `bin` onto `PATH` for their subprocesses, so they work
despite the host shell's broken PATH.

## Tool Response Contract

All tools exit 0 on success and 1 on failure. stdout is always valid JSON:

```
{"success": true,  "output": "<path>", "meta": {...}}
{"success": false, "error": "<msg>",  "stderr": "<raw>"}
```

## Conventions

- Never edit compiled outputs. Edit the source file and recompile.
- After any compile step, verify the output exists and report its file size.
- If a tool fails, report the exact error from `stderr` — do not guess or retry blindly.
- Templates live in `templates/`. Copy to `workspace/` before editing.
