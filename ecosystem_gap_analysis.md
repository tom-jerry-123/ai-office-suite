# MCP Ecosystem Gap Analysis — AI Office Suite

> What to build, what to adopt, and why. As of June 2026.

---

## The Three Gaps Worth Building

### 1. `quarto-mcp` — Slides & Document Rendering ★ Highest priority

**The gap:** No Quarto CLI MCP server exists anywhere. Zero. The closest thing
(`t-kalinowski/quartohelp`) is a doc-search tool, not a renderer. `mcp-pandoc`
covers basic format conversion but has no code-execution engine, no `.pptx`
output, and no Reveal.js support.

**Why it matters:** Quarto is the only tool in the stack that compiles a single
source file to PDF, PPTX, and Reveal.js. Without a Quarto MCP, slide authoring
requires manual CLI calls outside the agent loop. This is the largest
functionality gap in the entire office suite ecosystem.

**What to build:**
```
quarto_render(input, to=[pdf|pptx|revealjs|html|docx|typst], params={})
quarto_check()
quarto_inspect(input)
quarto_create(template, output_dir)
```
Wrap the Quarto CLI as a subprocess. Expose progress via MCP notifications.
Ship as `uvx quarto-mcp` so it runs with no extra Python install on the host.

---

### 2. `pdf-edit-mcp` — Core PDF Editing

**The gap:** Many PDF MCP repos exist but almost all are single-author study
projects (1–4 stars, no tests, last commit >6 months ago). `rsp2k/mcp-pdf` is
the best general-purpose option — well-engineered with 40 tools and proper
fallback chains — but it skews heavily toward extraction. Editing operations
(merge, compress, annotate, form fill) are present but secondary and
incomplete.

**Why it matters:** Merge, split, rotate, compress, redact, and form-fill are
the daily workhorses of any document pipeline. These need to work reliably
without a LaTeX source file or a running Docker service.

**What to build** (PyMuPDF-backed, ~15 focused tools):
```
merge, split_by_pages, split_by_bookmarks
rotate, crop
compress (pikepdf + Ghostscript fallback)
watermark_overlay
redact (with apply_redactions)
form_fill + form_flatten
annotation_add, annotation_list, annotation_delete
page_to_image (for vision-capable agent inspection)
```
Sandboxed working directory, deterministic output naming, JSON stdout contract.

**Note on Stirling-PDF:** skip it. Its value is OCR on scanned documents and
X.509 certificate signing — niche operations. PyMuPDF covers the 90% case
without a running Docker daemon. Add Stirling later, as an optional dependency,
only if you hit a concrete gap (e.g. signed PDFs with certificate chains).

---

### 3. `image-tools-mcp` — Image Processing & Optimization

**The gap:** `maoxiaoke/mcp-media-processor` wraps ImageMagick + FFmpeg for
video and image conversion but has no optimization path. `AeyeOps/mcp-imagemagick`
handles DNG→WebP only. No MCP server wraps oxipng, pngquant, or mozjpeg.
Batch processing over a directory is absent from all options.

**Why it matters:** Image optimization is a silent tax on every document
pipeline — oversized embedded images inflate PDF and PPTX file sizes. Without
an MCP-level abstraction, the agent has to shell out to multiple tools
with no unified interface.

**What to build** (Pillow in-process + subprocess-driven optimizers):
```
image_convert(input, format, quality)
image_resize(input, width, height, fit=[contain|cover|fill])
image_optimize(input, engine=[oxipng|pngquant|mozjpeg|webp], max_kb)
image_batch(glob, transform_pipeline)
image_strip_exif(input)
image_metadata(input)
```

---

## What to Adopt

| Tool | Repo | Notes |
|---|---|---|
| **DOCX editing** | `SecurityRonin/docx-mcp` | OOXML-level edits; real tracked changes, comments, footnotes. Best-in-class. |
| **DOCX styling** | `GongRzhe/Office-Word-MCP-Server` | 1.9k stars, **archived Mar 2026** — fork and pin v1.1.11. |
| **PPTX authoring** | `GongRzhe/Office-PowerPoint-MCP-Server` | 34 tools, 25+ templates, 1.3k stars, actively maintained. |
| **LaTeX compile** | `RobertoDure/mcp-latex-server` | Templates, syntax validation, sandboxed path. Best safety/feature balance. |
| **Format conversion** | `vivekVells/mcp-pandoc` | 507 stars, MIT, md→docx/pdf/html/epub. Stopgap for Quarto until quarto-mcp ships. |
| **Workspace retrieval** | `shinpr/mcp-local-rag` | SQLite + FTS5 + embeddings, local-only, indexes PDF/DOCX/MD, npm-published. |

---

## What to Avoid

- **`famano/mcp-server-office`** — toy implementation, 4 tools, images replaced
  with `[Image]` placeholders, no tracked changes.
- **`OfficeMCP/OfficeMCP`** — exposes a `RunPython(code)` tool that executes
  arbitrary code in the server process. README disclaims responsibility.
  Wrong shape for any agentic deployment.
- **COM/AppleScript Office servers generally** — Windows/macOS-only, stateful,
  not composable with a local-LLM future.
- **Any "MCP server" listed only on aggregator sites** (mcp.so, lobehub, glama)
  without a real GitHub repo with commits in the last 90 days.

---

## Summary

| Area | Action | Reason |
|---|---|---|
| Quarto / slides | **Build** `quarto-mcp` | No competitor exists |
| PDF editing | **Build** `pdf-edit-mcp` | Existing options too shallow or extraction-only |
| Image optimization | **Build** `image-tools-mcp` | No oxipng/pngquant MCP exists |
| DOCX | **Adopt** (fork Word server) | Well-covered; low ROI to rebuild |
| LaTeX | **Adopt** | Three solid options; pick RobertoDure |
| Workspace indexing | **Adopt** `mcp-local-rag` | Production-shaped, npm-distributed |
| Stirling-PDF | **Defer** | Useful only for OCR + cert signing; PyMuPDF covers the rest |
