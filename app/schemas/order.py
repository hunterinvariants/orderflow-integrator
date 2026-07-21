from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OrderStatus(StrEnum):
    draft = "draft"
    validated = "validated"
    routed = "routed"
    synced = "synced"
    failed = "failed"


class OrderItem(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=Decimal("0"))


class OrderCreateRequest(BaseModel):
    external_order_id: str = Field(min_length=1)
    source_system: str = Field(min_length=1)
    destination_system: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    currency: str | None = None
    items: list[OrderItem] = Field(min_length=1)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRouteRequest(BaseModel):
    integration_name: str = Field(min_length=1)
    transport_reference: str | None = None


class OrderRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    external_order_id: str
    source_system: str
    destination_system: str
    customer_id: str
    currency: str
    items: list[OrderItem]
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: OrderStatus = OrderStatus.draft
    total_amount: Decimal = Decimal("0")
    integration_name: str | None = None
    transport_reference: str | None = None
    events: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

