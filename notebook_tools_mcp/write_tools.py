"""Write tools for notebook-tools MCP server.

Index-based counterparts to Claude Code's built-in NotebookEdit (which uses
cell_id/cell_number). These stay consistent with nb_overview/nb_read_cell indexing.
"""

from __future__ import annotations

from notebook_tools_mcp import mcp
from notebook_tools_mcp._helpers import (
    load_notebook,
    save_notebook,
    get_cell_source,
    make_cell,
    source_to_lines,
)


@mcp.tool()
def nb_write_cell(notebook_path: str, cell_index: int, source: str) -> str:
    """Overwrite cell source by index (from nb_overview). All notebook-tools use positional indices, not cell IDs. Prefer this over NotebookEdit when working within the nb_overview workflow."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    if cell_index < 0 or cell_index >= len(cells):
        return f"Error: cell_index {cell_index} out of range (0-{len(cells) - 1})"

    cells[cell_index]["source"] = source_to_lines(source)

    try:
        save_notebook(notebook_path, nb)
    except OSError as e:
        return f"Error saving notebook: {e}"

    n_lines = len(source.split("\n"))
    n_chars = len(source)
    return f"Cell {cell_index} updated ({n_lines} lines, {n_chars} chars)"


@mcp.tool()
def nb_insert_cell(notebook_path: str, cell_index: int, cell_type: str, source: str) -> str:
    """Insert a new cell at position (use cell_index=-1 to append). Cell type must be 'code' or 'markdown'. Indices of subsequent cells shift by +1."""
    if cell_type not in ("code", "markdown"):
        return f"Error: cell_type must be 'code' or 'markdown', got '{cell_type}'"

    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    n_cells = len(cells)

    if cell_index == -1:
        actual_index = n_cells
    elif 0 <= cell_index <= n_cells:
        actual_index = cell_index
    else:
        return f"Error: cell_index {cell_index} out of range (-1 or 0-{n_cells})"

    cell = make_cell(cell_type, source)
    cells.insert(actual_index, cell)

    try:
        save_notebook(notebook_path, nb)
    except OSError as e:
        return f"Error saving notebook: {e}"

    total = len(cells)
    return f"Inserted {cell_type} cell at index {actual_index} ({total} cells total)"


@mcp.tool()
def nb_delete_cell(notebook_path: str, cell_index: int) -> str:
    """Delete a cell by index. Returns the first line of the deleted cell for confirmation. Indices of subsequent cells shift by -1."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    cells = nb["cells"]
    if cell_index < 0 or cell_index >= len(cells):
        return f"Error: cell_index {cell_index} out of range (0-{len(cells) - 1})"

    cell = cells[cell_index]
    cell_type = cell.get("cell_type", "unknown")
    src = get_cell_source(cell)
    first_line = src.split("\n")[0].rstrip() if src else ""
    if len(first_line) > 60:
        first_line = first_line[:57] + "..."

    del cells[cell_index]

    try:
        save_notebook(notebook_path, nb)
    except OSError as e:
        return f"Error saving notebook: {e}"

    remaining = len(cells)
    return f"Deleted cell {cell_index} ({cell_type}: {first_line}). {remaining} cells remaining."
