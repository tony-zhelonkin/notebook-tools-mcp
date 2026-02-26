"""Read tools for notebook-tools MCP server."""

from __future__ import annotations

from pathlib import Path

from notebook_tools_mcp import mcp
from notebook_tools_mcp._helpers import (
    load_notebook,
    get_cell_source,
    format_cell,
    human_readable_size,
    output_byte_size,
    heading_level,
    parse_cell_indices,
)


@mcp.tool()
def nb_metadata(notebook_path: str) -> str:
    """Notebook triage: kernel info, format version, cell counts, file size, output size. Use to decide if a notebook is worth exploring further."""
    try:
        nb = load_notebook(notebook_path)
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

    type_counts: dict[str, int] = {}
    total_output_bytes = 0
    for cell in cells:
        ct = cell.get("cell_type", "unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1
        total_output_bytes += output_byte_size(cell.get("outputs", []))

    type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))

    return (
        f"Notebook: {p.name}\n"
        f"Kernel: {kernel_display} ({kernel_lang})\n"
        f"Format: nbformat {nbformat}\n"
        f"Cells: {n_cells} ({type_str})\n"
        f"File size: {file_size_kb:.1f} KB\n"
        f"Total output size: {human_readable_size(total_output_bytes)}"
    )


@mcp.tool()
def nb_overview(notebook_path: str, include_output_sizes: bool = True) -> str:
    """START HERE for any .ipynb file. Lists all cells with index, type, line count, char count, and first-line preview. Use the cell indices in output to target nb_read_cell, nb_write_cell, etc."""
    try:
        nb = load_notebook(notebook_path)
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
        src = get_cell_source(cell)
        src_lines = src.split("\n")
        n_lines = len(src_lines)
        n_chars = len(src)
        first_line = src_lines[0].rstrip() if src_lines else ""
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."

        entry = f"{i:>3} | {abbrev:4} | {n_lines:>3}L | {n_chars:>5}C | {first_line}"

        if include_output_sizes and ct == "code":
            outputs = cell.get("outputs", [])
            if outputs:
                out_size = output_byte_size(outputs)
                entry += f" | out: {human_readable_size(out_size)}"

        lines.append(entry)

    return "\n".join(lines)


@mcp.tool()
def nb_read_cell(
    notebook_path: str,
    cell_index: int,
    include_outputs: bool = False,
    max_output_chars: int = 2000,
) -> str:
    """Read full source of one cell by index (from nb_overview). Use instead of the Read tool for .ipynb — avoids loading raw JSON. Set include_outputs=true only when you need execution output."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    if cell_index < 0 or cell_index >= len(cells):
        return f"Error: cell_index {cell_index} out of range (0-{len(cells) - 1})"

    return format_cell(cells[cell_index], cell_index, include_outputs, max_output_chars)


@mcp.tool()
def nb_read_cells(
    notebook_path: str,
    cell_indices: str,
    cell_type: str | None = None,
    include_outputs: bool = False,
    max_output_chars: int = 2000,
) -> str:
    """Batch-read cells by index range (e.g. '0,1,5-8'). More efficient than multiple nb_read_cell calls. Optional cell_type filter ('code' or 'markdown')."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    indices = parse_cell_indices(cell_indices, len(cells) - 1)

    if not indices:
        return f"Error: no valid cell indices in '{cell_indices}' (notebook has {len(cells)} cells)"

    results: list[str] = []
    for idx in indices:
        cell = cells[idx]
        if cell_type and cell.get("cell_type", "unknown") != cell_type:
            continue
        results.append(format_cell(cell, idx, include_outputs, max_output_chars))

    if not results:
        return f"Error: no cells matching type '{cell_type}' in indices '{cell_indices}'"

    return "\n---\n".join(results)


@mcp.tool()
def nb_read_section(
    notebook_path: str,
    header: str,
    max_cells: int = 50,
    include_outputs: bool = False,
    max_output_chars: int = 2000,
) -> str:
    """Read all cells under a markdown heading until the next same-or-higher-level heading. Use nb_headings first to see available headings. Falls back gracefully if heading structure is inconsistent."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    header_lower = header.lower()

    # Find the first markdown cell whose source contains the header (case-insensitive)
    start_index = None
    start_level = None
    for i, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        src = get_cell_source(cell)
        if header_lower in src.lower():
            # Determine heading level from first non-empty line
            for line in src.split("\n"):
                stripped = line.strip()
                if stripped:
                    level = heading_level(stripped)
                    if level is not None:
                        start_level = level
                    break
            start_index = i
            break

    if start_index is None:
        # List available headings
        available: list[str] = []
        for i, cell in enumerate(cells):
            if cell.get("cell_type") != "markdown":
                continue
            src = get_cell_source(cell)
            for line in src.split("\n"):
                stripped = line.strip()
                if stripped:
                    level = heading_level(stripped)
                    if level is not None:
                        available.append(f"  Cell {i:>3} | {stripped}")
                    break
        heading_list = "\n".join(available) if available else "  (no headings found)"
        return f"Error: no section matching '{header}' found.\n\nAvailable headings:\n{heading_list}"

    # Collect cells from start_index until same-level-or-higher heading or max_cells
    collected: list[str] = []
    for i in range(start_index, min(start_index + max_cells, len(cells))):
        cell = cells[i]
        # After the first cell, check if we hit a same-level-or-higher heading
        if i > start_index and cell.get("cell_type") == "markdown" and start_level is not None:
            src = get_cell_source(cell)
            for line in src.split("\n"):
                stripped = line.strip()
                if stripped:
                    level = heading_level(stripped)
                    if level is not None and level <= start_level:
                        # Reached next section boundary
                        return "\n---\n".join(collected)
                    break
        collected.append(format_cell(cell, i, include_outputs, max_output_chars))

    return "\n---\n".join(collected)


@mcp.tool()
def nb_headings(notebook_path: str) -> str:
    """List all markdown headings with cell indices and levels. Use before nb_read_section to see available section names."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    headings: list[str] = []

    for i, cell in enumerate(cells):
        if cell.get("cell_type") != "markdown":
            continue
        src = get_cell_source(cell)
        for line in src.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            level = heading_level(stripped)
            if level is not None:
                headings.append(f"Cell {i:>3} | {stripped}")
            break

    if not headings:
        return "No headings found in notebook."

    return "\n".join(headings)
