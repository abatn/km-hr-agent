#!/usr/bin/env python3
"""Minimaler Test-Connector für MCP-Test."""

from fastmcp import FastMCP

mcp = FastMCP("test-connector")

@mcp.tool()
def hello_world(name: str) -> dict:
    """Einfacher Test."""
    return {"message": f"Hallo {name}!", "status": "ok"}

@mcp.tool()
def get_test_data() -> dict:
    """Gibt Testdaten zurück."""
    return {
        "skills": 0.40,
        "erfahrung": 0.30,
        "assessment": 0.20,
        "bildung": 0.10,
        "quelle": "Test"
    }

if __name__ == "__main__":
    mcp.run()
