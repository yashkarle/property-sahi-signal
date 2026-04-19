from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.orchestrator import stream_chat
from app.dependencies import AuthDep

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    property_id: str | None = None
    active_bid_session: str | None = None


@router.post("")
async def chat_stream(request: ChatRequest, _: AuthDep) -> StreamingResponse:
    context = {
        "property_id": request.property_id,
        "session_id": request.session_id,
        "active_bid_session": request.active_bid_session,
    }

    def generate():
        for chunk in stream_chat(request.message, context):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
