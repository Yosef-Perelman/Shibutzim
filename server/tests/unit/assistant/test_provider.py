import pytest

from app.assistant.llm import GeminiLLM
from app.assistant.llm.provider import build_llm
from app.config import Settings
from app.core.errors import ServiceUnavailable


def test_build_llm_without_an_api_key_is_assistant_unavailable():
    with pytest.raises(ServiceUnavailable) as raised:
        build_llm(Settings(gemini_api_key=""))

    assert raised.value.code == "assistant_unavailable"


def test_build_llm_with_a_key_returns_the_gemini_adapter_with_the_configured_models():
    llm = build_llm(
        Settings(
            gemini_api_key="k", assistant_chat_model="chat-x", assistant_embedding_model="emb-x"
        )
    )

    assert isinstance(llm, GeminiLLM)
    assert llm.chat_model == "chat-x"
    assert llm.embedding_model == "emb-x"
    assert llm.embedding_dimensions == 768
