from typing import Generic, TypeVar, Sequence
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic cursor-based pagination response."""
    data: Sequence[T]
    next_cursor: str | None
    has_more: bool
