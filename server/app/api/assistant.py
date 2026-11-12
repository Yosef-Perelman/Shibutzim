from fastapi import APIRouter

from app.assistant import chat
from app.assistant.agent import AgentReply
from app.assistant.llm import Message
from app.deps import CurrentUser, LlmDep, NowDep, SessionDep
from app.schemas.assistant import ChatIn, ChatOut, ProposalOut, ToolCallOut

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/chat")
def post_chat(
    body: ChatIn, user: CurrentUser, session: SessionDep, now: NowDep, llm: LlmDep
) -> ChatOut:
    history = [Message(role=item.role, text=item.content) for item in body.messages]
    return chat_out(chat.answer(session, user, llm, history, now=now))


def chat_out(reply: AgentReply) -> ChatOut:
    return ChatOut(
        message=reply.text,
        citations=reply.citations,
        tool_calls=[ToolCallOut(name=call.name, args=call.args) for call in reply.tool_calls],
        proposal=ProposalOut.model_validate(reply.proposal) if reply.proposal else None,
    )
