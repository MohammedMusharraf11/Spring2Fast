"""
LLM provider — AWS Bedrock Llama 4 Maverick (single provider, no fallback chain).

┌─────────────────────────┬──────────────────────────────┬──────────────────────────┐
│ Task                    │ Model                        │ Temperature              │
├─────────────────────────┼──────────────────────────────┼──────────────────────────┤
│ Code generation         │ Llama 4 Maverick 17B         │ 0.0  (deterministic)     │
│ Analysis / enrichment   │ Llama 4 Maverick 17B         │ 0.1  (slight creativity) │
│ Planning                │ Llama 4 Maverick 17B         │ 0.0  (structured output) │
│ Validation (LLM judge)  │ Llama 4 Maverick 17B         │ 0.0  (strict compliance) │
└─────────────────────────┴──────────────────────────────┴──────────────────────────┘

No RPM limits — pay-per-token pricing on Bedrock.
No fallback chain — fail loudly if Bedrock is misconfigured.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.meta.llama4-maverick-17b-instruct-v1:0"


def _create_bedrock_model(
    temperature: float = 0.0,
    max_tokens: int = 8192,
) -> BaseChatModel:
    """Create a Bedrock Llama 4 Maverick instance.

    Raises RuntimeError if credentials are missing or the SDK is not installed.
    """
    if not settings.bedrock_aws_access_key_id or not settings.bedrock_aws_secret_access_key:
        raise RuntimeError(
            "AWS Bedrock credentials not configured. "
            "Set BEDROCK_AWS_ACCESS_KEY_ID and BEDROCK_AWS_SECRET_ACCESS_KEY in .env"
        )

    try:
        from langchain_aws import ChatBedrockConverse
    except ImportError as e:
        raise RuntimeError(
            "langchain-aws is not installed. Run: pip install langchain-aws"
        ) from e

    model = ChatBedrockConverse(
        model_id=BEDROCK_MODEL_ID,
        region_name=settings.bedrock_aws_region,
        aws_access_key_id=settings.bedrock_aws_access_key_id,
        aws_secret_access_key=settings.bedrock_aws_secret_access_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    logger.debug(f"Bedrock model ready: {BEDROCK_MODEL_ID} (temp={temperature})")
    return model


# ── Public API ────────────────────────────────────────────────────────────────

def get_code_model() -> BaseChatModel:
    """Model for code generation (converter agents).

    Temperature 0.0 — fully deterministic output for reproducible code.
    High max_tokens for generating full source files.
    """
    return _create_bedrock_model(temperature=0.0, max_tokens=8192)


def get_analysis_model() -> BaseChatModel:
    """Model for analysis and enrichment tasks.

    Temperature 0.1 — slight creativity for inferring technologies
    and summarizing business logic, but still grounded.
    """
    return _create_bedrock_model(temperature=0.1, max_tokens=4096)


def get_planning_model() -> BaseChatModel:
    """Model for migration planning — structured JSON output.

    Temperature 0.0 — no randomness for deterministic planning.
    """
    return _create_bedrock_model(temperature=0.0, max_tokens=4096)


def get_validation_model() -> BaseChatModel:
    """Model for LLM-as-judge validation (contract compliance).

    Temperature 0.0 — strict compliance checking, no creative liberties.
    """
    return _create_bedrock_model(temperature=0.0, max_tokens=2048)


# ── Backward compatibility aliases ───────────────────────────────────────────

def get_chat_model(
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Generic model accessor (backward compat). Prefer task-specific functions."""
    return _create_bedrock_model(
        temperature=temperature if temperature is not None else 0.1,
        max_tokens=max_tokens or 4096,
    )


def log_model_routing() -> None:
    """Log which model is active at startup."""
    has_creds = bool(
        settings.bedrock_aws_access_key_id and settings.bedrock_aws_secret_access_key
    )
    if has_creds:
        logger.info(f"🤖 LLM: AWS Bedrock — {BEDROCK_MODEL_ID} (region: {settings.bedrock_aws_region})")
    else:
        logger.error(
            "❌ AWS Bedrock credentials NOT configured. "
            "LLM features will fail. Set BEDROCK_AWS_ACCESS_KEY_ID and "
            "BEDROCK_AWS_SECRET_ACCESS_KEY in .env"
        )
