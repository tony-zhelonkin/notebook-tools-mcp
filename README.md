# notebook-tools-mcp

Read-only MCP server for Jupyter notebook navigation. Reads `.ipynb` files directly as JSON — no Jupyter server, no kernel, no overhead.

## Problem

AI CLI agents (Claude Code, Gemini CLI, Codex) working inside VS Code Dev Containers don`t seem yet to have a good way of interacting with Jupyter notebooks. Notebooks are JSON files where oftentimes 90%+ of the bytes are base64-encoded image outputs and execution metadata. Reading a 1MB notebook with a standard file-read tool wastes ~294K tokens on noise. Agents end up re-inventing notebook parsing logic every session, burning tokens on the same problem repeatedly.

I mostly work with claude code. Write operations are already handled — Claude Code has a built-in `NotebookEdit` tool for insert/replace/delete. The missing part for me was efficient *reading*.

## Design decisions

**No Jupyter server.** Personally, I mostly work with remote VS Code Remote Dev Containers (Docker) over SSH. Adding a Jupyter server means propagating that server stream to the local machine — extra memory, extra complexity, zero value for me when VS Code already renders notebooks natively.

**No dependencies beyond `mcp`.** Notebooks are JSON. Python's stdlib `json` module reads them perfectly. Pulling in `nbformat` (and its 50+ transitive Jupyter ecosystem deps) to parse a JSON file is unnecessary weight in a container environment.

**No write tools.** Claude Code's `NotebookEdit` handles insert, replace, and delete. Duplicating that here would create competing tools that confuse the agent. This server reads. `NotebookEdit` writes. Clean separation.

**No execution.** Running code requires a kernel, which requires a server. That's the complexity this tool exists to avoid. I execute via VS Code's notebook UI and convert to scripts for production.

**stdio transport only.** Launched on demand by the MCP client, communicates via stdin/stdout, exits when done. No HTTP endpoints, no WebSocket connections, no persistent processes.

## Install

```bash
# pip — install directly from GitHub
pip install git+https://github.com/tony-zhelonkin/notebook-tools-mcp.git

# uv — same, faster
uv pip install git+https://github.com/tony-zhelonkin/notebook-tools-mcp.git
```

For development (editable install from a local clone):

```bash
git clone https://github.com/tony-zhelonkin/notebook-tools-mcp.git
pip install -e notebook-tools-mcp/
```

## Configure

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "notebook-tools": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "notebook_tools_mcp.server"]
    }
  }
}
```

Or toggle via [SciAgent-toolkit](https://github.com/tony-zhelonkin/SciAgent-toolkit) addon system:

```bash
./scripts/manage-addon.sh enable notebook-tools --project-dir /path/to/project
./scripts/manage-addon.sh disable notebook-tools --project-dir /path/to/project
```

## Tools

All tools take `notebook_path` (absolute path) as first parameter.

| Tool | What it does |
|------|-------------|
| `nb_metadata` | Kernel info, cell counts, file/output sizes |
| `nb_overview` | Table-of-contents — index, type, line count, first-line preview |
| `nb_read_cell` | Single cell by index, optional output inclusion with truncation |
| `nb_read_cells` | Batch read via range syntax: `"0,1,5-8,12"` |
| `nb_search` | Regex search across cells with context lines, cell-type filter |

## Token economics

Against a 1.15 MB notebook (41 cells, 93% output data):

| Operation | Standard claude code `Read` | notebook-tools-mcp |
|---|---|---|
| Understand notebook structure | ~294K tokens (full file) | ~690 tokens (`nb_overview`) |
| Read one cell | ~294K tokens (full file) | ~100 tokens (`nb_read_cell`) |
| Find a specific cell | ~294K tokens (full file) + mental scan | ~50 tokens (`nb_search`) |
