"""
WebSocket connection manager for real-time events.
"""

from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
from datetime import datetime
import asyncio
from enum import Enum

from app.services.cache import CacheService
from app.services.auth_service import AuthService


class EventType(str, Enum):
    """WebSocket event types."""
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"
    MESSAGE = "message"
    NOTIFICATION = "notification"
    ORGANIZATION_UPDATE = "organization.update"
    USER_UPDATE = "user.update"
    POLICY_EVALUATION = "policy.evaluation"
    INVITATION_RECEIVED = "invitation.received"
    WEBHOOK_EVENT = "webhook.event"
    AUDIT_EVENT = "audit.event"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class ConnectionManager:
    """
    Manages WebSocket connections and message routing.
    """
    
    def __init__(self):
        # Active connections: {connection_id: {"websocket": ws, "user_id": id, "subscriptions": set()}}
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        
        # User to connection mapping: {user_id: set(connection_ids)}
        self.user_connections: Dict[str, Set[str]] = {}
        
        # Organization subscriptions: {org_id: set(connection_ids)}
        self.organization_subscribers: Dict[str, Set[str]] = {}
        
        # Topic subscriptions: {topic: set(connection_ids)}
        self.topic_subscribers: Dict[str, Set[str]] = {}
        
        # Cache service for distributed deployments
        self.cache = CacheService()
        
        # Connection ID counter
        self._connection_counter = 0
        
        # Background tasks
        self.background_tasks = set()
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> str:
        """
        Accept a new WebSocket connection.
        """
        await websocket.accept()
        
        # Generate connection ID
        self._connection_counter += 1
        connection_id = f"conn_{self._connection_counter}_{datetime.utcnow().timestamp()}"
        
        # Store connection
        self.active_connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "authenticated": False,
            "subscriptions": set(),
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }
        
        # Map user to connection if authenticated
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            self.active_connections[connection_id]["authenticated"] = True
        
        # Send connection confirmation
        await self.send_to_connection(connection_id, {
            "type": EventType.CONNECTION,
            "data": {
                "connection_id": connection_id,
                "status": "connected",
                "authenticated": bool(user_id)
            }
        })
        
        # Start ping/pong heartbeat
        task = asyncio.create_task(self._heartbeat(connection_id))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Disconnect and clean up a WebSocket connection.
        """
        if connection_id not in self.active_connections:
            return
        
        connection = self.active_connections[connection_id]
        
        # Remove from user connections
        if connection["user_id"]:
            user_id = connection["user_id"]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        
        # Remove from all subscriptions
        for org_id in list(self.organization_subscribers.keys()):
            self.organization_subscribers[org_id].discard(connection_id)
            if not self.organization_subscribers[org_id]:
                del self.organization_subscribers[org_id]
        
        for topic in list(self.topic_subscribers.keys()):
            self.topic_subscribers[topic].discard(connection_id)
            if not self.topic_subscribers[topic]:
                del self.topic_subscribers[topic]
        
        # Close WebSocket
        try:
            await connection["websocket"].close()
        except Exception:
            pass  # Intentionally ignoring - websocket may already be closed or in invalid state

        # Remove connection
        del self.active_connections[connection_id]
    
    async def authenticate(
        self,
        connection_id: str,
        auth_token: str,
        db_session
    ) -> bool:
        """
        Authenticate a WebSocket connection.
        """
        if connection_id not in self.active_connections:
            return False
        
        # Verify token
        auth_service = AuthService(db_session)
        user = await auth_service.verify_token(auth_token)
        
        if not user:
            await self.send_to_connection(connection_id, {
                "type": EventType.AUTHENTICATION,
                "data": {
                    "status": "failed",
                    "error": "Invalid authentication token"
                }
            })
            return False
        
        # Update connection
        connection = self.active_connections[connection_id]
        old_user_id = connection["user_id"]
        
        # Remove from old user mapping if exists
        if old_user_id and old_user_id != str(user.id):
            if old_user_id in self.user_connections:
                self.user_connections[old_user_id].discard(connection_id)
        
        # Update connection info
        connection["user_id"] = str(user.id)
        connection["authenticated"] = True
        connection["user_email"] = user.email
        connection["tenant_id"] = str(user.tenant_id)
        
        # Add to user connections
        if str(user.id) not in self.user_connections:
            self.user_connections[str(user.id)] = set()
        self.user_connections[str(user.id)].add(connection_id)
        
        # Send success response
        await self.send_to_connection(connection_id, {
            "type": EventType.AUTHENTICATION,
            "data": {
                "status": "success",
                "user_id": str(user.id),
                "email": user.email
            }
        })
        
        return True
    
    async def subscribe(
        self,
        connection_id: str,
        subscription_type: str,
        target_id: str
    ) -> bool:
        """
        Subscribe a connection to events.
        """
        if connection_id not in self.active_connections:
            return False
        
        connection = self.active_connections[connection_id]
        
        # Require authentication for subscriptions
        if not connection["authenticated"]:
            await self.send_to_connection(connection_id, {
                "type": EventType.ERROR,
                "data": {
                    "error": "Authentication required for subscriptions"
                }
            })
            return False
        
        # Add subscription based on type
        if subscription_type == "organization":
            if target_id not in self.organization_subscribers:
                self.organization_subscribers[target_id] = set()
            self.organization_subscribers[target_id].add(connection_id)
            connection["subscriptions"].add(f"org:{target_id}")
            
        elif subscription_type == "topic":
            if target_id not in self.topic_subscribers:
                self.topic_subscribers[target_id] = set()
            self.topic_subscribers[target_id].add(connection_id)
            connection["subscriptions"].add(f"topic:{target_id}")
        
        else:
            await self.send_to_connection(connection_id, {
                "type": EventType.ERROR,
                "data": {
                    "error": f"Unknown subscription type: {subscription_type}"
                }
            })
            return False
        
        # Confirm subscription
        await self.send_to_connection(connection_id, {
            "type": EventType.SUBSCRIPTION,
            "data": {
                "status": "subscribed",
                "type": subscription_type,
                "target": target_id
            }
        })
        
        return True
    
    async def unsubscribe(
        self,
        connection_id: str,
        subscription_type: str,
        target_id: str
    ) -> bool:
        """
        Unsubscribe a connection from events.
        """
        if connection_id not in self.active_connections:
            return False
        
        connection = self.active_connections[connection_id]
        
        # Remove subscription based on type
        if subscription_type == "organization":
            if target_id in self.organization_subscribers:
                self.organization_subscribers[target_id].discard(connection_id)
            connection["subscriptions"].discard(f"org:{target_id}")
            
        elif subscription_type == "topic":
            if target_id in self.topic_subscribers:
                self.topic_subscribers[target_id].discard(connection_id)
            connection["subscriptions"].discard(f"topic:{target_id}")
        
        # Confirm unsubscription
        await self.send_to_connection(connection_id, {
            "type": EventType.UNSUBSCRIPTION,
            "data": {
                "status": "unsubscribed",
                "type": subscription_type,
                "target": target_id
            }
        })
        
        return True
    
    async def send_to_connection(self, connection_id: str, message: dict):
        """
        Send a message to a specific connection.
        """
        if connection_id not in self.active_connections:
            return
        
        connection = self.active_connections[connection_id]
        try:
            await connection["websocket"].send_json(message)
        except Exception as e:
            print(f"Error sending to connection {connection_id}: {e}")
            await self.disconnect(connection_id)
    
    async def send_to_user(self, user_id: str, message: dict):
        """
        Send a message to all connections for a user.
        """
        if user_id not in self.user_connections:
            return
        
        for connection_id in list(self.user_connections[user_id]):
            await self.send_to_connection(connection_id, message)
    
    async def broadcast_to_organization(
        self,
        organization_id: str,
        message: dict,
        exclude_connection: Optional[str] = None
    ):
        """
        Broadcast a message to all subscribers of an organization.
        """
        if organization_id not in self.organization_subscribers:
            return
        
        for connection_id in list(self.organization_subscribers[organization_id]):
            if connection_id != exclude_connection:
                await self.send_to_connection(connection_id, message)
    
    async def broadcast_to_topic(
        self,
        topic: str,
        message: dict,
        exclude_connection: Optional[str] = None
    ):
        """
        Broadcast a message to all subscribers of a topic.
        """
        if topic not in self.topic_subscribers:
            return
        
        for connection_id in list(self.topic_subscribers[topic]):
            if connection_id != exclude_connection:
                await self.send_to_connection(connection_id, message)
    
    async def broadcast_to_all(
        self,
        message: dict,
        authenticated_only: bool = True
    ):
        """
        Broadcast a message to all connected clients.
        """
        for connection_id, connection in list(self.active_connections.items()):
            if not authenticated_only or connection["authenticated"]:
                await self.send_to_connection(connection_id, message)
    
    async def handle_message(
        self,
        connection_id: str,
        message: dict,
        db_session
    ):
        """
        Handle an incoming message from a client.
        """
        message_type = message.get("type")
        data = message.get("data", {})
        
        if message_type == EventType.AUTHENTICATION:
            # Handle authentication
            token = data.get("token")
            if token:
                await self.authenticate(connection_id, token, db_session)
        
        elif message_type == EventType.SUBSCRIPTION:
            # Handle subscription
            subscription_type = data.get("subscription_type")
            target_id = data.get("target_id")
            if subscription_type and target_id:
                await self.subscribe(connection_id, subscription_type, target_id)
        
        elif message_type == EventType.UNSUBSCRIPTION:
            # Handle unsubscription
            subscription_type = data.get("subscription_type")
            target_id = data.get("target_id")
            if subscription_type and target_id:
                await self.unsubscribe(connection_id, subscription_type, target_id)
        
        elif message_type == EventType.MESSAGE:
            # Handle custom message
            await self._handle_custom_message(connection_id, data, db_session)
        
        elif message_type == EventType.PING:
            # Respond to ping
            await self.send_to_connection(connection_id, {
                "type": EventType.PONG,
                "data": {"timestamp": datetime.utcnow().isoformat()}
            })
            if connection_id in self.active_connections:
                self.active_connections[connection_id]["last_ping"] = datetime.utcnow()
        
        else:
            # Unknown message type
            await self.send_to_connection(connection_id, {
                "type": EventType.ERROR,
                "data": {"error": f"Unknown message type: {message_type}"}
            })
    
    async def _handle_custom_message(
        self,
        connection_id: str,
        data: dict,
        db_session
    ):
        """
        Handle custom application messages.
        """
        # This is where you'd implement custom message handling logic
        # For example, chat messages, notifications, etc.
        
        connection = self.active_connections.get(connection_id)
        if not connection or not connection["authenticated"]:
            await self.send_to_connection(connection_id, {
                "type": EventType.ERROR,
                "data": {"error": "Authentication required"}
            })
            return
        
        # Example: Broadcast message to organization
        if "organization_id" in data:
            await self.broadcast_to_organization(
                data["organization_id"],
                {
                    "type": EventType.MESSAGE,
                    "data": {
                        "from": connection["user_email"],
                        "message": data.get("message", ""),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                exclude_connection=connection_id
            )
    
    async def _heartbeat(self, connection_id: str):
        """
        Send periodic heartbeat to keep connection alive.
        """
        while connection_id in self.active_connections:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
                if connection_id in self.active_connections:
                    # Check last ping
                    connection = self.active_connections[connection_id]
                    last_ping = connection.get("last_ping", connection["connected_at"])
                    
                    # Disconnect if no ping for 90 seconds
                    if (datetime.utcnow() - last_ping).seconds > 90:
                        print(f"Connection {connection_id} timed out")
                        await self.disconnect(connection_id)
                        break
                    
                    # Send ping
                    await self.send_to_connection(connection_id, {
                        "type": EventType.PING,
                        "data": {"timestamp": datetime.utcnow().isoformat()}
                    })
                    
            except Exception as e:
                print(f"Heartbeat error for {connection_id}: {e}")
                break
    
    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """
        Get information about a connection.
        """
        if connection_id not in self.active_connections:
            return None
        
        connection = self.active_connections[connection_id]
        return {
            "connection_id": connection_id,
            "user_id": connection.get("user_id"),
            "authenticated": connection.get("authenticated", False),
            "subscriptions": list(connection.get("subscriptions", set())),
            "connected_at": connection.get("connected_at"),
            "last_ping": connection.get("last_ping")
        }
    
    def get_stats(self) -> dict:
        """
        Get WebSocket connection statistics.
        """
        authenticated_count = sum(
            1 for c in self.active_connections.values()
            if c.get("authenticated", False)
        )
        
        return {
            "total_connections": len(self.active_connections),
            "authenticated_connections": authenticated_count,
            "unique_users": len(self.user_connections),
            "organization_topics": len(self.organization_subscribers),
            "custom_topics": len(self.topic_subscribers),
            "total_subscriptions": sum(
                len(c.get("subscriptions", set()))
                for c in self.active_connections.values()
            )
        }


# Global connection manager instance
manager = ConnectionManager()