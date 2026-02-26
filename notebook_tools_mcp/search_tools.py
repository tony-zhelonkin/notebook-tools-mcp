"""Search tools for notebook-tools MCP server."""

from __future__ import annotations

import re

from notebook_tools_mcp import mcp
from notebook_tools_mcp._helpers import (
    load_notebook,
    get_cell_source,
    find_notebooks,
)


def _search_cells(
    cells: list[dict],
    pattern: re.Pattern,
    cell_type: str | None,
    context_lines: int,
) -> list[str]:
    """Search cells for regex matches, returning formatted result blocks."""
    matches: list[str] = []

    for i, cell in enumerate(cells):
        ct = cell.get("cell_type", "unknown")
        if cell_type and ct != cell_type:
            continue

        src = get_cell_source(cell)
        src_lines = src.split("\n")

        for line_num, line in enumerate(src_lines):
            if not pattern.search(line):
                continue

            block: list[str] = []
            for offset in range(context_lines, 0, -1):
                bi = line_num - offset
                if bi >= 0:
                    block.append(f"    {src_lines[bi]}")

            block.append(f"  > Cell {i} ({ct}) L{line_num}: {line.rstrip()}")

            for offset in range(1, context_lines + 1):
                ai = line_num + offset
                if ai < len(src_lines):
                    block.append(f"    {src_lines[ai]}")

            matches.append("\n".join(block))

    return matches


@mcp.tool()
def nb_search(
    notebook_path: str,
    pattern: str,
    cell_type: str | None = None,
    context_lines: int = 1,
) -> str:
    """Regex search within ONE notebook. Use INSTEAD OF Grep for .ipynb files — Grep sees raw JSON, this sees cell source code. Returns cell index + line number + context for each match."""
    try:
        nb = load_notebook(notebook_path)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    matches = _search_cells(nb["cells"], regex, cell_type, context_lines)

    if not matches:
        return f"No matches found for: {pattern}"

    return f"Found {len(matches)} match(es) for: {pattern}\n\n" + "\n\n".join(matches)


@mcp.tool()
def nb_search_dir(
    directory: str,
    pattern: str,
    cell_type: str | None = None,
    context_lines: int = 0,
) -> str:
    """Regex search across ALL .ipynb files in a directory. Use to find which notebook defines a variable, imports a module, or contains a pattern. Results grouped by notebook."""
    try:
        notebooks = find_notebooks(directory)
    except ValueError as e:
        return f"Error: {e}"

    if not notebooks:
        return f"No notebooks found in: {directory}"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    total_matches = 0
    notebook_sections: list[str] = []

    for nb_path in notebooks:
        try:
            nb = load_notebook(str(nb_path))
        except (FileNotFoundError, ValueError):
            continue

        matches = _search_cells(nb["cells"], regex, cell_type, context_lines)
        if not matches:
            continue

        total_matches += len(matches)
        section = f"== {nb_path.name} ==\n" + "\n".join(matches)
        notebook_sections.append(section)

    if not notebook_sections:
        return f"No matches found for: {pattern}"

    header = (
        f"Found {total_matches} match(es) across "
        f"{len(notebook_sections)} notebook(s) for: {pattern}"
    )
    return header + "\n\n" + "\n\n".join(notebook_sections)
