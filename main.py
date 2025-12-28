import asyncio
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("better-auth")

# Constants
BETTER_AUTH_BASE = "https://www.better-auth.com"
USER_AGENT = "better-auth-mcp/1.0"


async def make_better_auth_request(url: str) -> str | None:
    """Fetch a plain text or markdown file from the Better Auth website with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain, text/markdown"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception:
            return None


@mcp.tool()
async def get_table_of_contents() -> str:
    """Fetch the Table of Contents (include routes to pages) from the Better Auth website."""
    url = f"{BETTER_AUTH_BASE}/llms.txt"
    data = await make_better_auth_request(url)
    if not data:
        return "Unable to fetch table of contents."
    return data

@mcp.tool()
async def read_page(page_route: str) -> str:
    """Read a page from the Better Auth website.

    Args:
        page_route: Route of the page to read (e.g. "/llms.txt/docs/basic-usage.md")
    """
    url = f"{BETTER_AUTH_BASE}{page_route}"
    data = await make_better_auth_request(url)
    if not data:
        return "Unable to fetch page."
    return data

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
    
