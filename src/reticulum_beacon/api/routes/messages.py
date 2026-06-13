"""LXMF message endpoints for the Reticulum Beacon API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...propagation.node import PropagationNode

router = APIRouter(tags=["messages"])


class SendMessageRequest(BaseModel):
    destination: str
    content: str
    title: str = ""


@router.get("/messages")
async def get_messages():
    """Get the message inbox.

    Note: LXMF stores messages on propagation nodes. This endpoint
    returns locally received messages if the propagation node is running.
    """
    pn = PropagationNode.get_instance()
    if not pn.is_running or pn.router is None:
        return {"messages": [], "total": 0}

    # Return basic stats for now; full inbox requires LXMF sync
    return {
        "messages": [],
        "stored_messages": len(pn.router.propagation_entries)
        if hasattr(pn.router, "propagation_entries")
        else 0,
    }


@router.post("/messages/send")
async def send_message(request: SendMessageRequest):
    """Send an LXMF message to a destination."""
    pn = PropagationNode.get_instance()
    if not pn.is_running:
        raise HTTPException(status_code=503, detail="Propagation node is not running")

    try:
        dest_hash = bytes.fromhex(request.destination)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid hex destination hash") from None

    try:
        msg_id = pn.send_message(dest_hash, request.content, title=request.title)
        if msg_id:
            return {"status": "sent", "message_id": msg_id.hex()}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
