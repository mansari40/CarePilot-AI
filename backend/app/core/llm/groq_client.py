"""LLM factory — reads model names and credentials from settings/env, never hardcodes them."""

from functools import lru_cache

from langchain_groq import ChatGroq

from app.config import get_settings


def get_llm(fast: bool = False) -> ChatGroq:
    """Return a configured ChatGroq client.

    The model is taken from settings (GROQ_MODEL / GROQ_MODEL_FAST env vars); the API key
    from GROQ_API_KEY.  Nothing is hardcoded here.  ``fast=True`` selects the lightweight
    variant for cheap steps.  A per-call timeout (default 45 s) prevents hung connections
    from blocking a workflow indefinitely.
    """
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to .env (see .env.example) before using the LLM."
        )
    model = settings.groq_model_fast if fast else settings.groq_model
    return ChatGroq(
        groq_api_key=settings.groq_api_key,
        model=model,
        temperature=0,
        timeout=settings.groq_timeout,
    )


@lru_cache
def get_cached_llm(fast: bool = False) -> ChatGroq:
    """Cached variant of :func:`get_llm` — ChatGroq clients are cheap and stateless."""
    return get_llm(fast=fast)