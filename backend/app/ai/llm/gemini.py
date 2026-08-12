from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


@lru_cache
def get_gemini_llm(*, temperature: float = 0.7) -> ChatGoogleGenerativeAI:
    """Return a cached ChatGoogleGenerativeAI client configured from settings."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
    )
