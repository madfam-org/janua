"""
Webhook management module for the Plinto SDK
"""

from typing import Dict, List, Optional, Any

from .http_client import HTTPClient
from .types import (
    WebhookEndpoint,
    WebhookEndpointCreateRequest,
    WebhookEndpointUpdateRequest,
    WebhookEvent,
    WebhookDelivery,
    WebhookEventType,
    WebhookEndpointListResponse,
)
from .utils import build_query_params, validate_webhook_signature


class WebhooksModule:
    """Webhook management operations"""
    
    def __init__(self, http_client: HTTPClient):
        self.http = http_client
    
    async def create_endpoint(
        self,
        request: WebhookEndpointCreateRequest
    ) -> WebhookEndpoint:
        """
        Create a new webhook endpoint
        
        Args:
            request: Webhook endpoint creation request
            
        Returns:
            Created webhook endpoint
        """
        response = await self.http.post(
            "/api/v1/webhooks/",
            json_data=request.dict()
        )
        return WebhookEndpoint(**response.json())
    
    async def list_endpoints(
        self,
        is_active: Optional[bool] = None
    ) -> WebhookEndpointListResponse:
        """
        List webhook endpoints for current user
        
        Args:
            is_active: Filter by active status
            
        Returns:
            List of webhook endpoints
        """
        params = build_query_params({"is_active": is_active})
        
        response = await self.http.get("/api/v1/webhooks/", params=params)
        data = response.json()
        
        return WebhookEndpointListResponse(
            endpoints=[WebhookEndpoint(**ep) for ep in data["endpoints"]],
            meta={
                "page": 1,
                "per_page": data["total"],
                "total": data["total"],
                "total_pages": 1
            }
        )
    
    async def get_endpoint(self, endpoint_id: str) -> WebhookEndpoint:
        """
        Get webhook endpoint details
        
        Args:
            endpoint_id: Webhook endpoint ID
            
        Returns:
            Webhook endpoint data
        """
        response = await self.http.get(f"/api/v1/webhooks/{endpoint_id}")
        return WebhookEndpoint(**response.json())
    
    async def update_endpoint(
        self,
        endpoint_id: str,
        request: WebhookEndpointUpdateRequest
    ) -> WebhookEndpoint:
        """
        Update webhook endpoint configuration
        
        Args:
            endpoint_id: Webhook endpoint ID
            request: Update request data
            
        Returns:
            Updated webhook endpoint
        """
        response = await self.http.patch(
            f"/api/v1/webhooks/{endpoint_id}",
            json_data=request.dict(exclude_unset=True)
        )
        return WebhookEndpoint(**response.json())
    
    async def delete_endpoint(self, endpoint_id: str) -> Dict[str, str]:
        """
        Delete webhook endpoint
        
        Args:
            endpoint_id: Webhook endpoint ID
            
        Returns:
            Success message
        """
        response = await self.http.delete(f"/api/v1/webhooks/{endpoint_id}")
        return response.json()
    
    async def test_endpoint(self, endpoint_id: str) -> Dict[str, str]:
        """
        Send test webhook to endpoint
        
        Args:
            endpoint_id: Webhook endpoint ID
            
        Returns:
            Success message
        """
        response = await self.http.post(f"/api/v1/webhooks/{endpoint_id}/test")
        return response.json()
    
    async def get_endpoint_stats(
        self,
        endpoint_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get webhook endpoint delivery statistics
        
        Args:
            endpoint_id: Webhook endpoint ID
            days: Number of days to include in stats
            
        Returns:
            Delivery statistics
        """
        params = build_query_params({"days": days})
        
        response = await self.http.get(
            f"/api/v1/webhooks/{endpoint_id}/stats",
            params=params
        )
        return response.json()
    
    async def list_events(
        self,
        endpoint_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List webhook events for an endpoint
        
        Args:
            endpoint_id: Webhook endpoint ID
            limit: Maximum events to return (1-1000)
            offset: Offset for pagination
            
        Returns:
            List of webhook events
        """
        params = build_query_params({
            "limit": limit,
            "offset": offset
        })
        
        response = await self.http.get(
            f"/api/v1/webhooks/{endpoint_id}/events",
            params=params
        )
        data = response.json()
        
        return {
            "events": [WebhookEvent(**event) for event in data["events"]],
            "total": data["total"]
        }
    
    async def list_deliveries(
        self,
        endpoint_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[WebhookDelivery]:
        """
        List webhook delivery attempts for an endpoint
        
        Args:
            endpoint_id: Webhook endpoint ID
            limit: Maximum deliveries to return (1-1000)
            offset: Offset for pagination
            
        Returns:
            List of webhook deliveries
        """
        params = build_query_params({
            "limit": limit,
            "offset": offset
        })
        
        response = await self.http.get(
            f"/api/v1/webhooks/{endpoint_id}/deliveries",
            params=params
        )
        return [WebhookDelivery(**delivery) for delivery in response.json()]
    
    async def regenerate_secret(self, endpoint_id: str) -> WebhookEndpoint:
        """
        Regenerate webhook endpoint secret
        
        Args:
            endpoint_id: Webhook endpoint ID
            
        Returns:
            Updated webhook endpoint with new secret
        """
        response = await self.http.post(
            f"/api/v1/webhooks/{endpoint_id}/regenerate-secret"
        )
        return WebhookEndpoint(**response.json())
    
    async def get_available_event_types(self) -> List[WebhookEventType]:
        """
        List all available webhook event types
        
        Returns:
            List of available event types
        """
        response = await self.http.get("/api/v1/webhooks/events/types")
        return [WebhookEventType(event_type) for event_type in response.json()]
    
    async def verify_signature(
        self,
        secret: str,
        payload: str,
        signature: str
    ) -> Dict[str, bool]:
        """
        Verify webhook signature for testing
        
        Args:
            secret: Webhook endpoint secret
            payload: Raw webhook payload
            signature: Signature to verify
            
        Returns:
            Verification result
        """
        response = await self.http.post(
            "/api/v1/webhooks/verify-signature",
            json_data={
                "secret": secret,
                "payload": payload,
                "signature": signature
            }
        )
        return response.json()
    
    @staticmethod
    def validate_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
        timestamp: Optional[str] = None,
        tolerance: int = 300
    ) -> bool:
        """
        Validate webhook signature locally
        
        Args:
            payload: Raw webhook payload string
            signature: Signature from X-Plinto-Signature header
            secret: Webhook endpoint secret
            timestamp: Timestamp from X-Plinto-Timestamp header
            tolerance: Maximum age of webhook in seconds
            
        Returns:
            True if signature is valid, False otherwise
        """
        return validate_webhook_signature(payload, signature, secret, timestamp, tolerance)