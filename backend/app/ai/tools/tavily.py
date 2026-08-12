from functools import lru_cache

from langchain_tavily import TavilySearch

from app.core.config import settings


@lru_cache
def get_tavily_search_tool(*, max_results: int = 5) -> TavilySearch:
    """Return a cached Tavily web search tool configured from settings."""
    return TavilySearch(
        max_results=max_results,
        tavily_api_key=settings.TAVILY_API_KEY,
    )
