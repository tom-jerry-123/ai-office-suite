# AI-Powered Office Suite

AI agents are transforming coding, but office -- not so much.
Many agent for office are currently built on tools for the agent to manipulate office document formats through the office user interface.
However, agents are terrible at using GUIs.
Instead, agent-based office tools should play on their strength -- code generation. This repo implements a system for agents to interact with source code to create and edit documents.

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

