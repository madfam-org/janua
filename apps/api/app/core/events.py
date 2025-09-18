"""Event emitter for application events"""

from typing import Dict, List, Callable, Any
from datetime import datetime
import asyncio
import structlog

logger = structlog.get_logger()


class EventEmitter:
    """Simple event emitter for application events"""
    
    def __init__(self):
        self._events: Dict[str, List[Callable]] = {}
        self._async_events: Dict[str, List[Callable]] = {}
        
    def on(self, event: str, handler: Callable):
        """Register an event handler"""
        if asyncio.iscoroutinefunction(handler):
            if event not in self._async_events:
                self._async_events[event] = []
            self._async_events[event].append(handler)
        else:
            if event not in self._events:
                self._events[event] = []
            self._events[event].append(handler)
            
    def off(self, event: str, handler: Callable):
        """Remove an event handler"""
        if event in self._events and handler in self._events[event]:
            self._events[event].remove(handler)
        if event in self._async_events and handler in self._async_events[event]:
            self._async_events[event].remove(handler)
            
    async def emit(self, event: str, *args, **kwargs):
        """Emit an event to all registered handlers"""
        # Log the event
        logger.info(f"Event emitted: {event}", 
                   timestamp=datetime.utcnow().isoformat(),
                   args=args, 
                   kwargs=kwargs)
        
        # Handle sync handlers
        if event in self._events:
            for handler in self._events[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in event handler for {event}", 
                               error=str(e))
                    
        # Handle async handlers
        if event in self._async_events:
            tasks = []
            for handler in self._async_events[event]:
                try:
                    tasks.append(handler(*args, **kwargs))
                except Exception as e:
                    logger.error(f"Error in async event handler for {event}", 
                               error=str(e))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
    def emit_sync(self, event: str, *args, **kwargs):
        """Synchronously emit an event (only for sync handlers)"""
        # Log the event
        logger.info(f"Event emitted (sync): {event}", 
                   timestamp=datetime.utcnow().isoformat(),
                   args=args, 
                   kwargs=kwargs)
        
        if event in self._events:
            for handler in self._events[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in event handler for {event}", 
                               error=str(e))