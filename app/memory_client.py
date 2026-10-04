from typing import Any

import httpx


DEFAULT_MEMORY_URL = "http://localhost:8090"


def store_memory(
    category: str,
    content: str,
    importance: int = 5,
    base_url: str = DEFAULT_MEMORY_URL,
) -> dict[str, Any]:
    response = httpx.post(
        f"{base_url}/memory/store",
        params={
            "category": category,
            "content": content,
            "importance": importance,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def search_memory(
    query: str,
    base_url: str = DEFAULT_MEMORY_URL,
) -> list[dict[str, Any]]:
    response = httpx.get(
        f"{base_url}/memory/search",
        params={
            "q": query,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()
