"""Webhook management module for the Janua SDK."""

from typing import Optional, Dict, Any, List
from datetime import datetime

from .http_client import HTTPClient
from .types import (
    WebhookEndpoint,
    WebhookEvent,
    WebhookDelivery,
    WebhookEventType,
    ListResponse,
    JanuaConfig,
)
from .utils import validate_webhook_signature


class WebhooksClient:
    """Client for webhook management operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the webhooks client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    # Endpoint management
    
    def create_endpoint(
        self,
        url: str,
        events: List[WebhookEventType],
        description: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WebhookEndpoint:
        """
        Create a new webhook endpoint.
        
        Args:
            url: Webhook endpoint URL
            events: List of event types to subscribe to
            description: Endpoint description
            enabled: Whether the endpoint is enabled
            metadata: Additional metadata
            
        Returns:
            Created WebhookEndpoint object
            
        Raises:
            ValidationError: If URL is invalid or events are empty
            AuthorizationError: If not authorized
            JanuaError: If creation fails
        """
        payload = {
            'url': url,
            'events': [e.value for e in events],
            'enabled': enabled,
            'metadata': metadata or {},
        }
        
        if description:
            payload['description'] = description
        
        response = self.http.post('/webhooks/endpoints', json=payload)
        data = response.json()
        return WebhookEndpoint(**data)
    
    def get_endpoint(self, endpoint_id: str) -> WebhookEndpoint:
        """
        Get a webhook endpoint by ID.
        
        Args:
            endpoint_id: Endpoint ID
            
        Returns:
            WebhookEndpoint object
            
        Raises:
            NotFoundError: If endpoint not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/webhooks/endpoints/{endpoint_id}')
        data = response.json()
        return WebhookEndpoint(**data)
    
    def list_endpoints(
        self,
        enabled: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListResponse[WebhookEndpoint]:
        """
        List webhook endpoints.
        
        Args:
            enabled: Filter by enabled status
            limit: Number of endpoints to return (max 100)
            offset: Number of endpoints to skip
            
        Returns:
            ListResponse containing endpoints and pagination info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if enabled is not None:
            params['enabled'] = enabled
        
        response = self.http.get('/webhooks/endpoints', params=params)
        data = response.json()
        
        return ListResponse[WebhookEndpoint](
            items=[WebhookEndpoint(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def update_endpoint(
        self,
        endpoint_id: str,
        url: Optional[str] = None,
        events: Optional[List[WebhookEventType]] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WebhookEndpoint:
        """
        Update a webhook endpoint.
        
        Args:
            endpoint_id: Endpoint ID
            url: New webhook URL
            events: New list of events to subscribe to
            description: New description
            enabled: New enabled status
            metadata: Updated metadata
            
        Returns:
            Updated WebhookEndpoint object
            
        Raises:
            NotFoundError: If endpoint not found
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if url is not None:
            payload['url'] = url
        if events is not None:
            payload['events'] = [e.value for e in events]
        if description is not None:
            payload['description'] = description
        if enabled is not None:
            payload['enabled'] = enabled
        if metadata is not None:
            payload['metadata'] = metadata
        
        response = self.http.patch(
            f'/webhooks/endpoints/{endpoint_id}',
            json=payload
        )
        data = response.json()
        return WebhookEndpoint(**data)
    
    def delete_endpoint(self, endpoint_id: str) -> None:
        """
        Delete a webhook endpoint.
        
        Args:
            endpoint_id: Endpoint ID
            
        Raises:
            NotFoundError: If endpoint not found
            AuthorizationError: If not authorized
            JanuaError: If deletion fails
        """
        self.http.delete(f'/webhooks/endpoints/{endpoint_id}')
    
    def rotate_secret(self, endpoint_id: str) -> WebhookEndpoint:
        """
        Rotate the signing secret for a webhook endpoint.
        
        Args:
            endpoint_id: Endpoint ID
            
        Returns:
            Updated WebhookEndpoint with new secret
            
        Raises:
            NotFoundError: If endpoint not found
            AuthorizationError: If not authorized
            JanuaError: If rotation fails
        """
        response = self.http.post(
            f'/webhooks/endpoints/{endpoint_id}/rotate-secret'
        )
        data = response.json()
        return WebhookEndpoint(**data)
    
    def test_endpoint(
        self,
        endpoint_id: str,
        event_type: Optional[WebhookEventType] = None,
    ) -> WebhookDelivery:
        """
        Send a test webhook to an endpoint.
        
        Args:
            endpoint_id: Endpoint ID
            event_type: Event type to test (defaults to ping)
            
        Returns:
            WebhookDelivery object with test results
            
        Raises:
            NotFoundError: If endpoint not found
            AuthorizationError: If not authorized
            JanuaError: If test fails
        """
        payload = {}
        if event_type:
            payload['event_type'] = event_type.value
        
        response = self.http.post(
            f'/webhooks/endpoints/{endpoint_id}/test',
            json=payload
        )
        data = response.json()
        return WebhookDelivery(**data)
    
    # Event management
    
    def list_events(
        self,
        endpoint_id: Optional[str] = None,
        event_type: Optional[WebhookEventType] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ListResponse[WebhookEvent]:
        """
        List webhook events.
        
        Args:
            endpoint_id: Filter by endpoint
            event_type: Filter by event type
            limit: Number of events to return (max 100)
            offset: Number of events to skip
            start_date: Filter events after this date
            end_date: Filter events before this date
            
        Returns:
            ListResponse containing events and pagination info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if endpoint_id:
            params['endpoint_id'] = endpoint_id
        if event_type:
            params['event_type'] = event_type.value
        if start_date:
            params['start_date'] = start_date.isoformat()
        if end_date:
            params['end_date'] = end_date.isoformat()
        
        response = self.http.get('/webhooks/events', params=params)
        data = response.json()
        
        return ListResponse[WebhookEvent](
            items=[WebhookEvent(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def get_event(self, event_id: str) -> WebhookEvent:
        """
        Get a webhook event by ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            WebhookEvent object
            
        Raises:
            NotFoundError: If event not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/webhooks/events/{event_id}')
        data = response.json()
        return WebhookEvent(**data)
    
    def replay_event(
        self,
        event_id: str,
        endpoint_id: Optional[str] = None,
    ) -> WebhookDelivery:
        """
        Replay a webhook event.
        
        Args:
            event_id: Event ID to replay
            endpoint_id: Specific endpoint to replay to (optional)
            
        Returns:
            WebhookDelivery object with replay results
            
        Raises:
            NotFoundError: If event not found
            AuthorizationError: If not authorized
            JanuaError: If replay fails
        """
        payload = {}
        if endpoint_id:
            payload['endpoint_id'] = endpoint_id
        
        response = self.http.post(
            f'/webhooks/events/{event_id}/replay',
            json=payload
        )
        data = response.json()
        return WebhookDelivery(**data)
    
    # Delivery management
    
    def list_deliveries(
        self,
        endpoint_id: Optional[str] = None,
        event_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListResponse[WebhookDelivery]:
        """
        List webhook deliveries.
        
        Args:
            endpoint_id: Filter by endpoint
            event_id: Filter by event
            status: Filter by delivery status (pending, success, failed)
            limit: Number of deliveries to return (max 100)
            offset: Number of deliveries to skip
            
        Returns:
            ListResponse containing deliveries and pagination info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if endpoint_id:
            params['endpoint_id'] = endpoint_id
        if event_id:
            params['event_id'] = event_id
        if status:
            params['status'] = status
        
        response = self.http.get('/webhooks/deliveries', params=params)
        data = response.json()
        
        return ListResponse[WebhookDelivery](
            items=[WebhookDelivery(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def get_delivery(self, delivery_id: str) -> WebhookDelivery:
        """
        Get a webhook delivery by ID.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            WebhookDelivery object
            
        Raises:
            NotFoundError: If delivery not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/webhooks/deliveries/{delivery_id}')
        data = response.json()
        return WebhookDelivery(**data)
    
    def retry_delivery(self, delivery_id: str) -> WebhookDelivery:
        """
        Retry a failed webhook delivery.
        
        Args:
            delivery_id: Delivery ID to retry
            
        Returns:
            Updated WebhookDelivery object
            
        Raises:
            NotFoundError: If delivery not found
            ValidationError: If delivery was successful
            AuthorizationError: If not authorized
            JanuaError: If retry fails
        """
        response = self.http.post(f'/webhooks/deliveries/{delivery_id}/retry')
        data = response.json()
        return WebhookDelivery(**data)
    
    # Utility methods
    
    def validate_signature(
        self,
        payload: Any,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Validate a webhook signature.
        
        Args:
            payload: Webhook payload (as string, bytes, or dict)
            signature: Signature from webhook headers
            secret: Webhook signing secret
            
        Returns:
            True if signature is valid, False otherwise
        """
        return validate_webhook_signature(payload, signature, secret)
    
    def get_event_types(self) -> List[Dict[str, str]]:
        """
        Get all available webhook event types.
        
        Returns:
            List of event types with descriptions
            
        Raises:
            JanuaError: If request fails
        """
        response = self.http.get('/webhooks/event-types')
        data = response.json()
        return data.get('event_types', [])