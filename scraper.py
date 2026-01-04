import asyncio
import os
import re
from typing import Dict, List, Optional

import httpx
from tqdm.asyncio import tqdm

from feature_store import FeatureStore

BETTER_AUTH_BASE = "https://www.better-auth.com"
USER_AGENT = "better-auth-mcp/1.0"


async def request_page(url: str) -> Optional[str]:
    """
    Request a page using a user agent.
    Args:
        url (str): The URL of the page to fetch.
    Returns:
        str | None: The page content or None if the request failed.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "text/plain, text/markdown"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception:
            return None


def parse_toc(toc_content: str) -> Dict[str, Dict[str, str]]:
    """
    Parse the table of contents from llms.txt to extract document routes with metadata.
    Extracts title from link text and description from text after the link.

    Args:
        toc_content (str): The content of the llms.txt file

    Returns:
        Dict[str, Dict[str, str]]: Dictionary mapping routes to metadata (description, title)
    """
    routes_metadata: Dict[str, Dict[str, str]] = {}
    lines = toc_content.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip category headers
        if re.match(r"^###\s+", line):
            continue

        # Extract title, route, and description from markdown
        # [title](route): description
        link_match = re.search(
            r"\[([^\]]+)\]\((/llms\.txt[^\)]+)\)(?:\s*:\s*(.+))?", line
        )
        if link_match:
            title = link_match.group(1).strip()
            route = link_match.group(2).strip()
            description = link_match.group(3).strip() if link_match.group(3) else ""

            routes_metadata[route] = {
                "description": description,
                "title": title,
            }

    return routes_metadata


async def fetch_document(
    route: str, metadata: Dict[str, str]
) -> Optional[Dict[str, str]]:
    """
    Fetch a single document from Better Auth.

    Args:
        route (str): Document route (e.g., "/llms.txt/docs/authentication/google.md").
        metadata (Dict[str, str]): Metadata from table of contents.

    Returns:
        Dict[str, str] | None: Dictionary with route, description, title, and content.
    """
    url = f"{BETTER_AUTH_BASE}{route}"
    content = await request_page(url)

    if content is None:
        return None

    return {
        "route": route,
        "description": metadata.get("description", ""),
        "title": metadata.get("title", ""),
        "content": content,
    }


async def scrape_all_docs(feature_store: FeatureStore) -> Dict[str, int]:
    """
    Scrape all Better Auth documentation and store in ChromaDB.

    Args:
        feature_store (FeatureStore): Initialized FeatureStore instance.

    Returns:
        Dict[str, int]: Dictionary with scraping statistics.
    """
    toc_url = f"{BETTER_AUTH_BASE}/llms.txt"
    print(f"Scraping table of contents from {toc_url}")
    toc_content = await request_page(toc_url)

    if not toc_content:
        raise Exception("Failed to fetch table of contents")

    routes_metadata = parse_toc(toc_content)
    routes = list(routes_metadata.keys())
    print(f"Found {len(routes)} document routes.")

    # Fetch all documents concurrently
    semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent requests

    async def fetch_with_semaphore(route: str):
        async with semaphore:
            return await fetch_document(route, routes_metadata[route])

    tasks = [fetch_with_semaphore(route) for route in routes]
    results = await tqdm.gather(*tasks, desc="Fetching", total=len(tasks))

    # Filter out None results and exceptions
    docs = []
    successful = 0
    failed = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Error fetching {routes[i]}: {result}")
            failed += 1
        elif result is None:
            print(f"Failed to fetch {routes[i]}")
            failed += 1
        else:
            docs.append(result)
            successful += 1

    print(f"\nFetched {successful} documents successfully, {failed} failed")

    print("Embedding and storing documents in ChromaDB")
    upserted_docs = feature_store.upsert_docs(docs)

    print(f"Upserted {upserted_docs} documents")

    return {
        "total_routes": len(routes),
        "successful": successful,
        "failed": failed,
        "upserted_docs": upserted_docs,
    }


async def main():
    persist_directory = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    print(f"Using ChromaDB persistence directory: {persist_directory}")

    feature_store = FeatureStore(persist_directory=persist_directory)
    stats = await scrape_all_docs(feature_store)


if __name__ == "__main__":
    asyncio.run(main())
