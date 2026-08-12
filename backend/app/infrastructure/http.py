from collections.abc import AsyncGenerator

import httpx

_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient]:
    """FastAPI dependency yielding a request-scoped async HTTP client."""
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        yield client
