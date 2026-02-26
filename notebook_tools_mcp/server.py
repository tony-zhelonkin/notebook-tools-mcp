"""Notebook Tools MCP Server — entry point."""

from notebook_tools_mcp import mcp

# Import tool modules to register @mcp.tool() decorators
import notebook_tools_mcp.read_tools    # noqa: F401
import notebook_tools_mcp.search_tools  # noqa: F401
import notebook_tools_mcp.write_tools   # noqa: F401


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
