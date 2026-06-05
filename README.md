# AI-Powered Office Suite

AI agents are transforming coding, but office -- not so much.
Many agent for office are currently built on tools for the agent to manipulate office document formats through the office user interface.
However, agents are terrible at using GUIs.
Instead, agent-based office tools should play on their strength -- code generation. This repo implements a system for agents to interact with source code to create and edit documents.

---

## In a nutshell

**Why build it?** AI agents transformed coding, but office work lagged behind. Most "AI for
office" tools puppeteer the application GUI (Word/PowerPoint via COM or AppleScript) — and agents
are bad at GUIs: those tools are stateful, OS-locked, and brittle. The real bottleneck is opaque
binary formats reached through a graphical interface. Our insight: play to an agent's strength,
**code generation**. The agent edits *source* it understands (`.md`, `.tex`, `.qmd`) and delegates
compiling opaque artifacts (`.pdf`, `.pptx`, `.docx`) to small, stateless tools.

**How does it work?** Two principles: **source-first** (the source file is canonical; compiled
outputs are derived) and **file-in / file-out** (every operation is a stateless transformation, no
GUI, no sessions). One conda env carries the heavy tools (tectonic, Quarto, pandoc, Pillow,
PyMuPDF); each is wrapped in a Python script with a uniform JSON-on-stdout contract. Those same
tools are then exposed as **six local stdio MCP servers** — `quarto`, `latex`, `pdf-edit`, `image`,
`docx`, and a SQLite/FTS5 workspace `index` — **18 tools** an agent (e.g. Claude Code) calls
directly. The MCP layer is model-agnostic: the same servers can front a local LLM later with no
changes (see the three-horizon plan in `office_suite_master_plan.md`).

**Who is it for?** Anyone who produces documents and wants to own the pipeline: researchers
typesetting LaTeX papers, teams generating decks from a prompt, batch image optimization, merging
and compressing PDFs, exporting Markdown to `.docx` for collaborators — all from plain language.
Because it runs locally and is model-agnostic, documents never have to leave your machine and you
are not locked into a cloud office suite.

**What's next?** More sophisticated PDF / document / image editing skills and scripts —
programmatic DOCX editing (tracked changes, find-replace), PDF redaction / form-fill / watermark /
annotation, embedding-based semantic search in the indexer, external image optimizers, and the
swap to a fully local model.

> **Evaluation & AI disclosure.** Every MCP server ships a smoke test, and all six pass a real
> stdio MCP client handshake (18 tools verified). Build-vs-adopt decisions and accepted limitations
> (keyword vs. semantic search; PyMuPDF vs. pikepdf compression) are documented in
> `ecosystem_gap_analysis.md` and `dev_history/`. Built with Claude Code via a phased lead/worker
> workflow; evaluated and adopted third-party repos are cited in the gap analysis.

---

## Demo

Everything runs inside the `office-suite` conda env:

```bash
conda activate office-suite
```

Two ways to drive the suite: **CLI tools** (work immediately) or **MCP servers** (for an agent).

### 1. CLI tools (`tools/`)

Each tool prints JSON to stdout (`{"success": ..., "output": ..., "meta": ...}`) and writes outputs to `workspace/`.

```bash
# Slides: Quarto .qmd -> revealjs / pdf / pptx
python tools/slides_tool.py render --input templates/quarto/slides.qmd --format revealjs

# LaTeX: .tex -> PDF
python tools/latex_tool.py compile --input templates/latex/article.tex --output-dir workspace

# PDF editing (PyMuPDF)
python tools/pdf_tool.py pdf-merge --input a.pdf --input b.pdf --output workspace/merged.pdf
python tools/pdf_tool.py pdf-page-to-image --input workspace/merged.pdf --page 1 --output workspace/p1.png

# Workspace index (SQLite FTS5)
python tools/index_tool.py build --dir workspace
python tools/index_tool.py search --query "quarto"

# Images (Pillow)
python tools/image_tool.py image-convert --input in.png --output workspace/out.webp --format WEBP
python tools/image_tool.py image-optimize --input in.png --output workspace/out.jpg --max-kb 200

# DOCX export (pandoc)
python tools/docx_tool.py from-markdown --input notes.md --output workspace/notes.docx
```

### 2. MCP servers (`mcp_servers/`)

Six stdio MCP servers wrap the tools above: **quarto, latex, pdf-edit, index, image, docx** (18 tools total).

- **In Claude Code:** they're registered in `.mcp.json` — **restart Claude Code** to load them, then call tools like `quarto_render`, `pdf_merge`, `index_search`, `image_optimize`, `docx_from_markdown`.
- **In another client** (Claude Desktop / `mcp-agent`): copy the portable registry `config/mcp_servers.json`. For a fresh machine, copy `.mcp.json.example` to `.mcp.json` and fill in absolute paths.

Verify all servers boot and list their tools:

```bash
python - <<'PY'
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
CFG = json.load(open(".mcp.json"))["mcpServers"]
async def main():
    for name, s in CFG.items():
        async with stdio_client(StdioServerParameters(command=s["command"], args=s["args"], env=s.get("env"))) as (r, w):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                tools = await sess.list_tools()
                print(name, "->", [t.name for t in tools.tools])
asyncio.run(main())
PY
```

Each server's smoke test also runs standalone, e.g. `python mcp_servers/quarto_mcp/smoke_test.py`.

---

# AI Disclosure

AI was used for conducting initial research for this project. Specifically, I identified several core capabilities I want - slideshows (quarto), pdfs, images - and asked AI to conduct Deep Research on tools that already accomplish these. This research informed what I decided to build vs. adopt, see `ecosystem_gap_analysis.md`.

No existing MCPs were actually adopted due to missing dependencies, mostly related to js. This project used many CLI and python lib tools, see `env/environment.yml`.

AI was used in planning and writing code for this project. 
