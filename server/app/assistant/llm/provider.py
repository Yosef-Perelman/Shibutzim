"""Chooses the model implementation from settings. A missing key means the assistant is off."""

from app.assistant.llm.gemini import UNAVAILABLE_MESSAGE, GeminiLLM
from app.assistant.llm.types import LLM
from app.config import Settings, get_settings
from app.core.errors import ServiceUnavailable
from app.models.handbook_chunk import EMBEDDING_DIMENSIONS


def build_llm(settings: Settings) -> LLM:
    if not settings.gemini_api_key:
        raise ServiceUnavailable(message=UNAVAILABLE_MESSAGE)
    return GeminiLLM(
        api_key=settings.gemini_api_key,
        chat_model=settings.assistant_chat_model,
        embedding_model=settings.assistant_embedding_model,
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        timeout_seconds=settings.assistant_timeout_seconds,
    )


def get_llm() -> LLM:
    """FastAPI dependency; tests replace it with a `FakeLLM`."""
    return build_llm(get_settings())
