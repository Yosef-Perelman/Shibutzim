import pytest

from app.assistant.llm import (
    ChatResult,
    EmbedTask,
    FakeLLM,
    Message,
    ToolCall,
    ToolDefinition,
    basis_vector,
    call_tool,
    say,
)

TOOL = ToolDefinition(name="get_my_hours", description="Hours.", parameters={"type": "object"})


def test_fake_llm_returns_scripted_replies_in_order():
    llm = FakeLLM([call_tool("get_my_hours", start="2026-03-01"), say("You worked 8 hours.")])

    first = llm.chat("system", [Message.user("hours?")], [TOOL])
    second = llm.chat("system", [Message.user("hours?")], [TOOL])

    assert first.tool_calls == (
        ToolCall(id="call_1", name="get_my_hours", args={"start": "2026-03-01"}),
    )
    assert first.text == ""
    assert second == ChatResult(text="You worked 8 hours.", tool_calls=())


def test_fake_llm_records_every_chat_call():
    llm = FakeLLM([say("ok")])
    history = [Message.user("hi")]

    llm.chat("be brief", history, [TOOL])

    assert len(llm.chat_calls) == 1
    recorded = llm.chat_calls[0]
    assert recorded.system == "be brief"
    assert recorded.messages == tuple(history)
    assert recorded.tools == (TOOL,)


def test_fake_llm_fails_loudly_when_the_script_runs_out():
    llm = FakeLLM([])

    with pytest.raises(AssertionError, match="no scripted reply"):
        llm.chat("system", [Message.user("hi")], [])


def test_fake_llm_embeds_known_texts_with_the_given_vectors_and_records_the_task():
    llm = FakeLLM([], embeddings={"overtime": basis_vector(0), "swaps": basis_vector(1)})

    vectors = llm.embed(["swaps", "overtime"], EmbedTask.query)

    assert vectors == [basis_vector(1), basis_vector(0)]
    assert llm.embed_calls == [(("swaps", "overtime"), EmbedTask.query)]


def test_fake_llm_refuses_to_embed_an_unscripted_text():
    llm = FakeLLM([], embeddings={"overtime": basis_vector(0)})

    with pytest.raises(AssertionError, match="no scripted embedding for 'unknown'"):
        llm.embed(["unknown"])


def test_basis_vector_has_768_dimensions_and_a_single_one():
    vector = basis_vector(3)

    assert len(vector) == 768
    assert vector[3] == 1.0
    assert sum(vector) == 1.0


def test_message_constructors_set_the_role():
    assert Message.user("hi").role == "user"
    assert Message.assistant("hello").role == "assistant"
