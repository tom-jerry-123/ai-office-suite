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

Two local stdio MCP servers are registered in `.mcp.json` (and `config/mcp_servers.json`).
They wrap the CLI tools above and return the same JSON contract. Restart Claude Code to load them.

### quarto (`mcp_servers/quarto_mcp/server.py`)

- `quarto_render(input, format, output_dir?)` — format ∈ `revealjs|pdf|pptx`. Wraps `slides_tool.py`.
- `quarto_create(template, output_dir)` — copies a `templates/quarto/` template into `workspace/<output_dir>/`.
- `quarto_check()` — runs `quarto check`.

### latex (`mcp_servers/latex_mcp/server.py`)

- `latex_compile(input, output_dir?, engine?)` — engine ∈ `tectonic|pdflatex`. Wraps `latex_tool.py`.
  Defaults `output_dir` to `workspace/` (never the source dir).

Both servers inject the conda-env `bin` onto `PATH` for their subprocesses, so they work
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

## Out of scope (not yet built)

`pdf_tool.py` / pdf-edit-mcp, workspace indexing, `image_tool.py` / image-tools-mcp,
and docx export are planned for later phases.
