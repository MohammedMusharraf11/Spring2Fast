"""Helpers for constructing the application's chat model."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def get_chat_model(
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel | None:
    """Return the configured chat model with a priority fallback chain.

    Priority: Groq → Gemini → OpenAI → None.
    """
    provider = settings.llm_provider.lower()
    temp = temperature if temperature is not None else 0.1
    tokens = max_tokens or 16384

    # Priority 1: Groq (fastest, free tier)
    if provider in {"auto", "groq"} and settings.groq_api_key:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.llm_model or "meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=temp,
            max_tokens=tokens,
            api_key=settings.groq_api_key,
        )

    # Priority 2: Google Gemini
    if provider in {"auto", "google", "gemini"} and settings.google_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.llm_model or "gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=temp,
        )

    # Priority 3: OpenAI
    if provider in {"auto", "openai"} and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=temp,
        )

    return None


def get_code_model() -> BaseChatModel | None:
    """Return a model optimized for code generation (low temperature, high tokens)."""
    return get_chat_model(temperature=0.05, max_tokens=32768)
