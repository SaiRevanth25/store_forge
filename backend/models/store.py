from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class StoreEngineEnum(str, Enum):
    """Supported store engines."""
    MEDUSA = "medusa"


class StoreStatusEnum(str, Enum):
    """Store provisioning status."""
    PROVISIONING = "PROVISIONING"
    READY = "READY"
    FAILED = "FAILED"
    DELETING = "DELETING"


class StoreEventResponse(BaseModel):
    """Event log entry for a store."""
    event_id: str
    store_id: str
    action: str
    message: str
    created_at: datetime


class StoreResponse(BaseModel):
    """Response model for store details."""
    store_id: str
    user_id: str
    engine: str
    status: str
    namespace: str
    helm_release: str
    store_url: str | None = None
    error_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StoreListResponse(BaseModel):
    """Response model for store list."""
    stores: list[StoreResponse]
    total: int


class CreateStoreRequest(BaseModel):
    """Request model for creating a store."""
    engine: StoreEngineEnum = Field(
        ..., 
        description="Store engine type: 'woocommerce' or 'medusa'"
    )
    name: str | None = Field(
        default=None,
        max_length=63,
        description="Store name (optional, used in namespace generation)"
    )


class CreateStoreResponse(BaseModel):
    """Response model for store creation."""
    store_id: str
    status: str
    message: str
    namespace: str


class DeleteStoreResponse(BaseModel):
    """Response model for store deletion."""
    store_id: str
    message: str


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str
    code: str | None = None
