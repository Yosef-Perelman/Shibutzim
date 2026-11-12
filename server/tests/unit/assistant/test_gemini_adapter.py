from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.assistant.llm import EmbedTask, Message, ToolCall, ToolDefinition, ToolResult
from app.assistant.llm.gemini import GeminiLLM, to_config, to_contents
from app.core.errors import ServiceUnavailable

SCHEMA = {"type": "object", "properties": {"start": {"type": "string"}}, "required": ["start"]}
TOOL = ToolDefinition(name="get_my_hours", description="Hours worked.", parameters=SCHEMA)


class StubModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(("generate", kwargs))
        if self.error:
            raise self.error
        return self.response

    def embed_content(self, **kwargs):
        self.calls.append(("embed", kwargs))
        if self.error:
            raise self.error
        return self.response


def make_llm(response=None, error=None) -> tuple[GeminiLLM, StubModels]:
    models = StubModels(response, error)
    llm = GeminiLLM(
        api_key="test-key",
        chat_model="chat-model",
        embedding_model="embedding-model",
        embedding_dimensions=768,
        timeout_seconds=30,
        client=SimpleNamespace(models=models),
    )
    return llm, models


def reply(*parts: types.Part) -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=list(parts))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def test_to_contents_maps_user_assistant_and_tool_messages():
    history = [
        Message.user("How many hours?"),
        Message.assistant(
            "Let me look.",
            tool_calls=(ToolCall("call_1", "get_my_hours", {"start": "2026-03-01"}, b"sig"),),
        ),
        Message.tool((ToolResult("call_1", "get_my_hours", {"hours": "8.00"}),)),
        Message.assistant("You worked 8 hours."),
    ]

    contents = to_contents(history)

    assert [content.role for content in contents] == ["user", "model", "user", "model"]
    assert contents[0].parts[0].text == "How many hours?"
    assert contents[1].parts[0].text == "Let me look."
    call_part = contents[1].parts[1]
    assert call_part.function_call.name == "get_my_hours"
    assert call_part.function_call.args == {"start": "2026-03-01"}
    assert call_part.function_call.id is None  # the Gemini API matches results by order
    assert call_part.thought_signature == b"sig"
    result_part = contents[2].parts[0]
    assert result_part.function_response.name == "get_my_hours"
    assert result_part.function_response.response == {"hours": "8.00"}
    assert contents[3].parts[0].text == "You worked 8 hours."


def test_to_config_declares_tools_with_json_schema_and_turns_automatic_calling_off():
    config = to_config("be brief", [TOOL])

    assert config.system_instruction == "be brief"
    declaration = config.tools[0].function_declarations[0]
    assert declaration.name == "get_my_hours"
    assert declaration.description == "Hours worked."
    assert declaration.parameters_json_schema == SCHEMA
    assert config.automatic_function_calling.disable is True
    assert config.temperature == 0.0


def test_to_config_without_tools_declares_none():
    assert to_config("be brief", []).tools is None


def test_chat_returns_the_text_of_a_text_reply():
    llm, models = make_llm(reply(types.Part(text="You worked 8 hours.")))

    result = llm.chat("system", [Message.user("hours?")], [TOOL])

    assert result.text == "You worked 8 hours."
    assert result.tool_calls == ()
    kind, kwargs = models.calls[0]
    assert kind == "generate"
    assert kwargs["model"] == "chat-model"
    assert kwargs["contents"][0].parts[0].text == "hours?"


def test_chat_returns_tool_calls_with_generated_ids_and_signatures():
    response = reply(
        types.Part(
            function_call=types.FunctionCall(name="get_my_hours", args={"start": "2026-03-01"}),
            thought_signature=b"sig",
        ),
        types.Part(function_call=types.FunctionCall(name="explain_pay", args=None)),
    )
    llm, _ = make_llm(response)

    result = llm.chat("system", [Message.user("hours and pay?")], [TOOL])

    assert result.text == ""
    assert result.tool_calls == (
        ToolCall("call_1", "get_my_hours", {"start": "2026-03-01"}, b"sig"),
        ToolCall("call_2", "explain_pay", {}, None),
    )


def test_chat_ignores_thought_parts_in_the_text():
    llm, _ = make_llm(
        reply(types.Part(text="thinking...", thought=True), types.Part(text="Answer."))
    )

    assert llm.chat("system", [Message.user("hi")], []).text == "Answer."


def test_chat_with_no_candidates_returns_an_empty_result():
    llm, _ = make_llm(types.GenerateContentResponse(candidates=None))

    result = llm.chat("system", [Message.user("hi")], [])

    assert result.text == ""
    assert result.tool_calls == ()


@pytest.mark.parametrize("error_class", [errors.ServerError, errors.ClientError])
def test_chat_maps_provider_errors_to_assistant_unavailable(error_class):
    llm, _ = make_llm(error=error_class(500, {"error": {"message": "boom"}}))

    with pytest.raises(ServiceUnavailable) as raised:
        llm.chat("system", [Message.user("hi")], [])

    assert raised.value.code == "assistant_unavailable"
    assert raised.value.status_code == 503
    assert "boom" not in raised.value.message


def test_embed_returns_one_vector_per_text_and_asks_for_the_configured_dimensions():
    response = types.EmbedContentResponse(
        embeddings=[
            types.ContentEmbedding(values=[0.1, 0.2]),
            types.ContentEmbedding(values=[0.3, 0.4]),
        ]
    )
    llm, models = make_llm(response)

    vectors = llm.embed(["a", "b"], EmbedTask.document)

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    kind, kwargs = models.calls[0]
    assert kind == "embed"
    assert kwargs["model"] == "embedding-model"
    assert kwargs["contents"] == ["a", "b"]
    assert kwargs["config"].output_dimensionality == 768
    assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_uses_the_query_task_for_questions():
    response = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[1.0])])
    llm, models = make_llm(response)

    llm.embed(["swap a shift?"], EmbedTask.query)

    assert models.calls[0][1]["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_fails_when_the_provider_returns_a_different_number_of_vectors():
    response = types.EmbedContentResponse(embeddings=[types.ContentEmbedding(values=[1.0])])
    llm, _ = make_llm(response)

    with pytest.raises(ServiceUnavailable):
        llm.embed(["a", "b"], EmbedTask.document)


def test_embed_maps_provider_errors_to_assistant_unavailable():
    llm, _ = make_llm(error=errors.ServerError(503, {"error": {"message": "down"}}))

    with pytest.raises(ServiceUnavailable):
        llm.embed(["a"], EmbedTask.document)
