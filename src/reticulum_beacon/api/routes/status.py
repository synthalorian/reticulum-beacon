"""Status endpoints for the Reticulum Beacon API."""

from fastapi import APIRouter

from ...node import BeaconNode
from ...propagation.node import PropagationNode

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status():
    """Return full node status including transport, interfaces, and propagation."""
    node = BeaconNode.get_instance()
    status_data = node.get_status()

    # Add propagation details if running
    pn = PropagationNode.get_instance()
    if pn.is_running:
        pn_status = pn.get_status()
        status_data["propagation"] = {
            "running": True,
            "uptime_seconds": pn_status.get("uptime_seconds", 0),
            "peers": pn_status.get("peers", 0),
            "stored_messages": pn_status.get("stored_messages", 0),
            "delivery_destination": pn_status.get("delivery_destination"),
        }

    return status_data


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    node = BeaconNode.get_instance()
    return {
        "status": "ok" if node.is_running else "stopped",
        "uptime_seconds": node.uptime,
    }
