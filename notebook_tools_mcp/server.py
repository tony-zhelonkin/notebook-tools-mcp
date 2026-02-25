#!/usr/bin/env python3
"""Notebook Tools MCP Server — lightweight read/search for Jupyter notebooks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notebook-tools")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_notebook(path: str) -> dict:
    """Load and validate a notebook JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Notebook not found: {path}")
    if not p.suffix == ".ipynb":
        raise ValueError(f"Not a notebook file (expected .ipynb): {path}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            nb = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in notebook: {e}")
    if "cells" not in nb:
        raise ValueError(f"Invalid notebook format: missing 'cells' key")
    return nb


def _parse_cell_indices(spec: str, max_index: int) -> list[int]:
    """Parse '0,1,5-8' into [0, 1, 5, 6, 7, 8], clamped to valid range."""
    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            tokens = part.split("-", 1)
            try:
                start = max(0, int(tokens[0].strip()))
                end = min(max_index, int(tokens[1].strip()))
            except ValueError:
                continue
            indices.extend(range(start, end + 1))
        else:
            try:
                idx = int(part)
                if 0 <= idx <= max_index:
                    indices.append(idx)
            except ValueError:
                continue
    return indices


def _format_output(output: dict, max_chars: int) -> str:
    """Extract text from a notebook output dict."""
    output_type = output.get("output_type", "")
    parts: list[str] = []

    if output_type == "stream":
        text = output.get("text", [])
        parts.append("".join(text) if isinstance(text, list) else str(text))

    elif output_type in ("execute_result", "display_data"):
        data = output.get("data", {})
        # Check for images first
        for mime in ("image/png", "image/jpeg", "image/svg+xml"):
            if mime in data:
                content = data[mime]
                if isinstance(content, list):
                    content = "".join(content)
                parts.append(f"[IMAGE: {mime}, {len(content)} chars base64]")
        # Then text
        if "text/plain" in data:
            text = data["text/plain"]
            parts.append("".join(text) if isinstance(text, list) else str(text))
        elif "text/html" in data:
            text = data["text/html"]
            parts.append("".join(text) if isinstance(text, list) else str(text))

    elif output_type == "error":
        traceback = output.get("traceback", [])
        parts.append("\n".join(traceback))

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... [truncated, {len(result)} total chars]"
    return result


def _human_readable_size(n_bytes: int) -> str:
    """Convert bytes to '1.2 KB', '3.4 MB' etc."""
    if n_bytes < 1024:
        return f"{n_bytes} B"
    elif n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    elif n_bytes < 1024 * 1024 * 1024:
        return f"{n_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{n_bytes / (1024 * 1024 * 1024):.1f} GB"


def _output_byte_size(outputs: list[dict]) -> int:
    """Total serialized size of outputs in bytes."""
    return len(json.dumps(outputs).encode("utf-8")) if outputs else 0


def _get_cell_source(cell: dict) -> str:
    """Get cell source as a single string."""
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def nb_metadata(notebook_path: str) -> str:
    """Return notebook metadata: kernel info, format version, cell counts, file size, output size."""
    try:
        nb = _load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    p = Path(notebook_path)
    file_size_kb = p.stat().st_size / 1024

    meta = nb.get("metadata", {})
    ks = meta.get("kernelspec", {})
    kernel_lang = ks.get("language", meta.get("language_info", {}).get("name", "unknown"))
    kernel_display = ks.get("display_name", "unknown")
    nbformat = f"{nb.get('nbformat', '?')}.{nb.get('nbformat_minor', '?')}"

    cells = nb["cells"]
    n_cells = len(cells)

    # Cell type counts
    type_counts: dict[str, int] = {}
    total_output_bytes = 0
    for cell in cells:
        ct = cell.get("cell_type", "unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1
        total_output_bytes += _output_byte_size(cell.get("outputs", []))

    type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))

    return (
        f"Notebook: {p.name}\n"
        f"Kernel: {kernel_display} ({kernel_lang})\n"
        f"Format: nbformat {nbformat}\n"
        f"Cells: {n_cells} ({type_str})\n"
        f"File size: {file_size_kb:.1f} KB\n"
        f"Total output size: {_human_readable_size(total_output_bytes)}"
    )


@mcp.tool()
def nb_overview(notebook_path: str, include_output_sizes: bool = True) -> str:
    """List all cells with index, type, line count, and first line preview. Quick table-of-contents for a notebook."""
    try:
        nb = _load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    p = Path(notebook_path)

    n_code = sum(1 for c in cells if c.get("cell_type") == "code")
    n_md = sum(1 for c in cells if c.get("cell_type") == "markdown")
    lines: list[str] = [f"# {p.name}: {len(cells)} cells ({n_code} code, {n_md} markdown)"]

    for i, cell in enumerate(cells):
        ct = cell.get("cell_type", "unknown")
        abbrev = "code" if ct == "code" else "md" if ct == "markdown" else ct[:4]
        src = _get_cell_source(cell)
        src_lines = src.split("\n")
        n_lines = len(src_lines)
        first_line = src_lines[0].rstrip() if src_lines else ""
        if len(first_line) > 80:
            first_line = first_line[:77] + "..."

        entry = f"{i:>3} | {abbrev:4} | {n_lines:>3}L | {first_line}"

        if include_output_sizes and ct == "code":
            outputs = cell.get("outputs", [])
            if outputs:
                out_size = _output_byte_size(outputs)
                entry += f" | out: {_human_readable_size(out_size)}"

        lines.append(entry)

    return "\n".join(lines)


@mcp.tool()
def nb_read_cell(
    notebook_path: str,
    cell_index: int,
    include_outputs: bool = False,
    max_output_chars: int = 2000,
) -> str:
    """Read the full source of a single cell by index. Optionally include cell outputs."""
    try:
        nb = _load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    if cell_index < 0 or cell_index >= len(cells):
        return f"Error: cell_index {cell_index} out of range (0-{len(cells) - 1})"

    cell = cells[cell_index]
    ct = cell.get("cell_type", "unknown")
    src = _get_cell_source(cell)
    n_lines = len(src.split("\n"))
    cell_id = cell.get("id", "none")

    header = f"# Cell {cell_index} ({ct}) | {n_lines} lines | id: {cell_id}"
    parts = [header, src]

    if include_outputs and cell.get("outputs"):
        parts.append("\n--- OUTPUT ---")
        output_texts: list[str] = []
        for out in cell["outputs"]:
            output_texts.append(_format_output(out, max_output_chars))
        combined = "\n".join(output_texts)
        if len(combined) > max_output_chars:
            combined = combined[:max_output_chars] + f"\n... [truncated, {len(combined)} total chars]"
        parts.append(combined)

    return "\n".join(parts)


@mcp.tool()
def nb_read_cells(
    notebook_path: str,
    cell_indices: str,
    include_outputs: bool = False,
    max_output_chars: int = 2000,
) -> str:
    """Read multiple cells by index. Accepts comma-separated indices or ranges (e.g. '0,1,5-8,12')."""
    try:
        nb = _load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    indices = _parse_cell_indices(cell_indices, len(cells) - 1)

    if not indices:
        return f"Error: no valid cell indices in '{cell_indices}' (notebook has {len(cells)} cells)"

    results: list[str] = []
    for idx in indices:
        cell = cells[idx]
        ct = cell.get("cell_type", "unknown")
        src = _get_cell_source(cell)
        n_lines = len(src.split("\n"))
        cell_id = cell.get("id", "none")

        header = f"# Cell {idx} ({ct}) | {n_lines} lines | id: {cell_id}"
        parts = [header, src]

        if include_outputs and cell.get("outputs"):
            parts.append("\n--- OUTPUT ---")
            output_texts: list[str] = []
            for out in cell["outputs"]:
                output_texts.append(_format_output(out, max_output_chars))
            combined = "\n".join(output_texts)
            if len(combined) > max_output_chars:
                combined = combined[:max_output_chars] + f"\n... [truncated, {len(combined)} total chars]"
            parts.append(combined)

        results.append("\n".join(parts))

    return "\n---\n".join(results)


@mcp.tool()
def nb_search(
    notebook_path: str,
    pattern: str,
    cell_type: str | None = None,
    context_lines: int = 1,
) -> str:
    """Search notebook cells for a regex pattern. Optionally filter by cell type ('code' or 'markdown')."""
    try:
        nb = _load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    cells = nb["cells"]
    matches: list[str] = []

    for i, cell in enumerate(cells):
        ct = cell.get("cell_type", "unknown")
        if cell_type and ct != cell_type:
            continue

        src = _get_cell_source(cell)
        src_lines = src.split("\n")

        for line_num, line in enumerate(src_lines):
            if regex.search(line):
                # Build context
                ctx_before = []
                for offset in range(context_lines, 0, -1):
                    bi = line_num - offset
                    if bi >= 0:
                        ctx_before.append(f"    {src_lines[bi]}")

                ctx_after = []
                for offset in range(1, context_lines + 1):
                    ai = line_num + offset
                    if ai < len(src_lines):
                        ctx_after.append(f"    {src_lines[ai]}")

                block = [f"Cell {i} ({ct}) L{line_num}: {line.rstrip()}"]
                if ctx_before:
                    block = ctx_before + block
                if ctx_after:
                    block.extend(ctx_after)

                # Mark the match line distinctly within context
                formatted = []
                for bl in block:
                    if bl.startswith("Cell "):
                        formatted.append(f"  > {bl}")
                    else:
                        formatted.append(bl)
                matches.append("\n".join(formatted))

    if not matches:
        return f"No matches found for: {pattern}"

    return f"Found {len(matches)} match(es) for: {pattern}\n\n" + "\n\n".join(matches)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
