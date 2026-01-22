"""
WebSocket endpoint for real-time communication.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from typing import Optional
import json

from app.database import get_db
from app.services.websocket_manager import manager, EventType
from app.services.auth_service import AuthService
from app.utils.logger import create_logger

logger = create_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Authentication token"),
    db=Depends(get_db),
):
    """
    Main WebSocket endpoint for real-time communication.

    Connection URL: ws://localhost:8000/ws?token=<auth_token>

    Message Format:
    {
        "type": "authentication|subscription|message|ping",
        "data": {
            // Type-specific data
        }
    }
    """
    connection_id = None

    try:
        # Authenticate if token provided
        user_id = None
        if token:
            auth_service = AuthService(db)
            user = await auth_service.verify_token(token)
            if user:
                user_id = str(user.id)

        # Accept connection
        connection_id = await manager.connect(websocket, user_id=user_id)

        # If token was provided, authenticate immediately
        if token and user_id:
            await manager.authenticate(connection_id, token, db)

        # Handle messages
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                # Parse message
                message = json.loads(data)

                # Handle message
                await manager.handle_message(connection_id, message, db)

            except json.JSONDecodeError:
                # Send error for invalid JSON
                await manager.send_to_connection(
                    connection_id,
                    {"type": EventType.ERROR, "data": {"error": "Invalid JSON format"}},
                )
            except Exception as e:
                # Send error for other exceptions
                await manager.send_to_connection(
                    connection_id, {"type": EventType.ERROR, "data": {"error": str(e)}}
                )

    except WebSocketDisconnect:
        # Client disconnected
        if connection_id:
            await manager.disconnect(connection_id)

    except Exception as e:
        # Unexpected error
        logger.error(f"WebSocket error: {e}", exc_info=True)
        if connection_id:
            await manager.disconnect(connection_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    """
    return manager.get_stats()


@router.get("/ws/connections/{connection_id}")
async def get_connection_info(connection_id: str):
    """
    Get information about a specific connection.
    """
    info = manager.get_connection_info(connection_id)
    if not info:
        return {"error": "Connection not found"}
    return info


# Event broadcasting endpoints (for internal use)


@router.post("/ws/broadcast/user/{user_id}")
async def broadcast_to_user(user_id: str, event_type: str, data: dict):
    """
    Broadcast an event to all connections for a user.
    """
    await manager.send_to_user(user_id, {"type": event_type, "data": data})

    return {"status": "sent", "user_id": user_id}


@router.post("/ws/broadcast/organization/{organization_id}")
async def broadcast_to_organization(organization_id: str, event_type: str, data: dict):
    """
    Broadcast an event to all subscribers of an organization.
    """
    await manager.broadcast_to_organization(organization_id, {"type": event_type, "data": data})

    return {"status": "sent", "organization_id": organization_id}


@router.post("/ws/broadcast/topic/{topic}")
async def broadcast_to_topic(topic: str, event_type: str, data: dict):
    """
    Broadcast an event to all subscribers of a topic.
    """
    await manager.broadcast_to_topic(topic, {"type": event_type, "data": data})

    return {"status": "sent", "topic": topic}


@router.post("/ws/broadcast/all")
async def broadcast_to_all(event_type: str, data: dict, authenticated_only: bool = True):
    """
    Broadcast an event to all connected clients.
    """
    await manager.broadcast_to_all(
        {"type": event_type, "data": data}, authenticated_only=authenticated_only
    )

    return {"status": "sent", "authenticated_only": authenticated_only}
