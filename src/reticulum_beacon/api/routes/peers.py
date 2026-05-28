"""Peers and interfaces endpoints for the Reticulum Beacon API."""

import RNS
from fastapi import APIRouter

from ...node import BeaconNode
from ...propagation.node import PropagationNode

router = APIRouter(tags=["peers"])


@router.get("/peers")
async def get_peers():
    """Return discovered peers from the propagation node."""
    peers_list = []
    pn = PropagationNode.get_instance()

    if pn.is_running and pn.router is not None and hasattr(pn.router, "peers") and pn.router.peers:
        for peer_hash, peer in pn.router.peers.items():
            peers_list.append(
                {
                    "hash": RNS.hexrep(peer_hash)
                    if isinstance(peer_hash, bytes)
                    else str(peer_hash),
                    "alive": getattr(peer, "alive", False),
                    "last_heard": getattr(peer, "last_heard", 0),
                    "name": getattr(peer, "name", None),
                    "rx_bytes": getattr(peer, "rx_bytes", 0),
                    "tx_bytes": getattr(peer, "tx_bytes", 0),
                }
            )

    return {"peers": peers_list, "total": len(peers_list)}


@router.get("/interfaces")
async def get_interfaces():
    """Return active Reticulum interfaces."""
    interfaces_list = []
    beacon = BeaconNode.get_instance()

    if beacon.is_running:
        try:
            from RNS import Transport

            if hasattr(Transport, "interfaces") and Transport.interfaces is not None:
                for iface in Transport.interfaces:
                    interfaces_list.append(
                        {
                            "name": getattr(iface, "name", "unknown"),
                            "type": type(iface).__name__,
                            "enabled": getattr(iface, "enabled", True),
                            "online": getattr(iface, "online", False),
                            "bytes_in": getattr(iface, "bytes_in", 0),
                            "bytes_out": getattr(iface, "bytes_out", 0),
                        }
                    )
        except Exception:
            pass

    return {"interfaces": interfaces_list, "total": len(interfaces_list)}
