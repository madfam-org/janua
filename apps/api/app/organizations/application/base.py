"""
Base classes for CQRS pattern
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

# Type variables for commands, queries, and results
TCommand = TypeVar('TCommand')
TQuery = TypeVar('TQuery')
TResult = TypeVar('TResult')


class Command(ABC):
    """Base class for commands (write operations)"""


class Query(ABC):
    """Base class for queries (read operations)"""


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Base class for command handlers"""

    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle the command and return result"""


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Base class for query handlers"""

    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """Handle the query and return result"""


class ApplicationError(Exception):
    """Base class for application layer errors"""

    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__


class ValidationError(ApplicationError):
    """Raised when validation fails"""


class NotFoundError(ApplicationError):
    """Raised when a resource is not found"""


class PermissionError(ApplicationError):
    """Raised when user lacks required permissions"""


class ConflictError(ApplicationError):
    """Raised when there's a business rule conflict"""
