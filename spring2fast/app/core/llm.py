"""

Task-specific LLM routing — 3-tier model strategy.

┌─────────────────────────┬──────────────────────────────┬────────────────────────────────────┐
│ Task                    │ Model                        │ Why                                │
├─────────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Code generation         │ Bedrock Llama 4 Maverick     │ Strong code, no rate-limit pain    │
│   (converter agents)    │   us.meta.llama4-maverick... │ AWS pays-per-token, no RPM cap     │
├─────────────────────────┼──────────────────────────────┼────────────────────────────────────┤
│ Analysis / Planning     │ Bedrock Llama 4 Maverick     │ No RPM cap → safe for 3 parallel   │
│   (tech, biz, plan)     │ → Groq Scout → Gemini Flash  │ analysis nodes firing at once      │
└─────────────────────────┴──────────────────────────────┴────────────────────────────────────┘

Why Bedrock for analysis too:
  - 3 parallel analysis nodes (tech_discover, extract_business, discover_components)
    ALL fire LLM calls simultaneously → Groq free tier 429s instantly on larger repos
  - Bedrock has no RPM cap, so parallel analysis is safe

Fallback chain:
  Code:     Bedrock → Groq → Gemini
  Analysis: Bedrock → Groq → Gemini
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

# ── Llama 4 Maverick model IDs on Bedrock (cross-region inference) ────────────
# us-east-1 supports: us.meta.llama4-maverick-17b-instruct-v1:0
# us-west-2 supports same via cross-region profile
BEDROCK_MAVERICK_MODEL = "us.meta.llama4-maverick-17b-instruct-v1:0"


def _bedrock_model(temperature: float = 0.05, max_tokens: int = 8192) -> BaseChatModel | None:
    """Llama 4 Maverick via AWS Bedrock — primary code generation model.

    Uses ChatBedrockConverse (Converse API) per LangChain docs.
    No RPM limits — pay-per-token pricing.
    """
    if not settings.bedrock_aws_access_key_id or not settings.bedrock_aws_secret_access_key:
        return None
    try:
        from langchain_aws import ChatBedrockConverse
        model = ChatBedrockConverse(
            model_id=BEDROCK_MAVERICK_MODEL,
            region_name=settings.bedrock_aws_region,
            aws_access_key_id=settings.bedrock_aws_access_key_id,
            aws_secret_access_key=settings.bedrock_aws_secret_access_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.debug(f"Bedrock model ready: {BEDROCK_MAVERICK_MODEL}")
        return model
    except Exception as e:
        logger.warning(f"Bedrock unavailable ({e}), falling back")
        return None


def _groq_model(temperature: float = 0.1, max_tokens: int = 8192) -> BaseChatModel | None:
    """Groq Llama 4 Scout — primary analysis model (fast, free tier)."""
    if not settings.groq_api_key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.llm_model or "meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=temperature,
            max_tokens=min(max_tokens, 8192),
            api_key=settings.groq_api_key,
        )
    except Exception as e:
        logger.warning(f"Groq unavailable ({e}), falling back")
        return None


def _gemini_model(temperature: float = 0.1, max_tokens: int = 8192) -> BaseChatModel | None:
    """Gemini Flash — last-resort fallback for both tiers."""
    if not settings.google_api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )
    except Exception as e:
        logger.warning(f"Gemini unavailable ({e}), falling back")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_code_model() -> BaseChatModel | None:
    """Model for code generation (converter agents).

    Priority: Bedrock Llama 4 Maverick → Groq Scout → Gemini Flash

    Bedrock is preferred because:
    - No RPM rate limits (pay-per-use)
    - Llama 4 Maverick is stronger at code than Scout
    - Eliminates the 429 retry waits that slow down conversion
    """
    model = _bedrock_model(temperature=0.05, max_tokens=8192)
    if model:
        logger.info(f"Code model: Bedrock ({BEDROCK_MAVERICK_MODEL})")
        return model
    model = _groq_model(temperature=0.05, max_tokens=8192)
    if model:
        logger.info("Code model: Groq (Bedrock unavailable)")
        return model
    model = _gemini_model(temperature=0.05)
    if model:
        logger.info("Code model: Gemini (last resort)")
        return model
    logger.error("No code model available!")
    return None


def get_chat_model(
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel | None:
    """Model for analysis, planning, enrichment tasks.

    Priority: Bedrock Maverick → Groq Scout → Gemini Flash

    Changed from Groq-first to Bedrock-first because:
    - The 3 parallel analysis nodes (tech_discover, extract_business, discover_components)
      all fire simultaneously, instantly hitting Groq's free-tier 30 RPM limit.
    - Bedrock has no RPM cap — parallel analysis is completely safe.
    - Groq kept as fallback in case Bedrock is unavailable.
    """
    temp = temperature if temperature is not None else 0.1
    tokens = max_tokens or 8192
    # Try Bedrock first (no RPM limit — safe for parallel nodes)
    model = _bedrock_model(temperature=temp, max_tokens=tokens)
    if model:
        return model
    # Fallback: Groq (fast but rate-limited)
    model = _groq_model(temperature=temp, max_tokens=tokens)
    if model:
        logger.warning("Analysis model: Groq (Bedrock unavailable) — may 429 on large repos")
        return model
    # Last resort: Gemini
    return _gemini_model(temperature=temp, max_tokens=tokens)


def get_analysis_model() -> BaseChatModel | None:
    """Alias for analysis/enrichment tasks."""
    return get_chat_model(temperature=0.1)


def get_planning_model() -> BaseChatModel | None:
    """Model for migration planning — low temperature for structured output."""
    return get_chat_model(temperature=0.0)


def log_model_routing() -> None:
    """Log which model is active for each tier at startup."""
    bedrock_ok = bool(settings.bedrock_aws_access_key_id and settings.bedrock_aws_secret_access_key)
    code = "Bedrock Llama4-Maverick" if bedrock_ok else (
        "Groq" if settings.groq_api_key else "Gemini" if settings.google_api_key else "NONE"
    )
    analysis = "Bedrock Llama4-Maverick" if bedrock_ok else (
        "Groq" if settings.groq_api_key else "Gemini" if settings.google_api_key else "NONE"
    )
    if not bedrock_ok and settings.groq_api_key:
        logger.warning(
            "⚠️  Bedrock not configured — analysis nodes will use Groq. "
            "Parallel analysis may hit 429 rate limits on repos with many components."
        )
    logger.info(f"🤖 LLM Routing — Code: [{code}]  Analysis: [{analysis}]")
