import httpx
import modal
from fastapi import FastAPI
from fastmcp import FastMCP

BETTER_AUTH_BASE = "https://www.better-auth.com"
USER_AGENT = "better-auth-mcp/1.0"

app = modal.App("example-mcp-server-stateless")

image = modal.Image.debian_slim(python_version="3.12").uv_pip_install(
    "fastapi==0.115.14",
    "fastmcp==2.10.6",
    "pydantic==2.11.10",
)


async def make_better_auth_request(url: str) -> str | None:
    """
    Fetch a plain text or markdown file from the Better Auth website with proper error handling.

    Args:
        url (str): The URL of the page to fetch.
    Returns:
        str | None: The text of the page or None if the request failed.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain, text/markdown"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception:
            return None


def make_mcp_server():
    """
    Create the MCP server and tools.

    Returns:
        FastMCP: The MCP server with the tools.
    """
    # Initialize FastMCP server
    mcp = FastMCP("better-auth")

    @mcp.tool()
    async def get_table_of_contents() -> str:
        """
        Fetch the Table of Contents (include routes to pages) from the Better Auth website.

        Returns:
            str: The table of contents.
        """
        url = f"{BETTER_AUTH_BASE}/llms.txt"
        data = await make_better_auth_request(url)
        if not data:
            return "Unable to fetch table of contents."
        return data

    @mcp.tool()
    async def read_page(page_route: str) -> str:
        """Read a page from the Better Auth website.

        Args:
            page_route (str): Route of the page to read (e.g. "/llms.txt/docs/basic-usage.md")
        Returns:
            str: The page content.
        """
        url = f"{BETTER_AUTH_BASE}{page_route}"
        data = await make_better_auth_request(url)
        if not data:
            return "Unable to fetch page."
        return data

    return mcp


@app.function(image=image)
@modal.asgi_app()
def web() -> FastAPI:
    """
    ASGI web endpoint for the MCP server.

    Returns:
        FastAPI: The FastAPI app.
    """
    mcp = make_mcp_server()
    mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)

    fastapi_app = FastAPI(lifespan=mcp_app.router.lifespan_context)
    fastapi_app.mount("/", mcp_app, "mcp")

    return fastapi_app
