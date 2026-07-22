from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OrderStatus(StrEnum):
    validated = "validated"
    queued = "queued"
    routed = "routed"
    synced = "synced"
    failed = "failed"


class OrderItem(BaseModel):
    sku: str = Field(min_length=1, max_length=120)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=Decimal("0"))


class OrderCreateRequest(BaseModel):
    external_order_id: str = Field(min_length=1, max_length=120)
    source_system: str = Field(min_length=1, max_length=50)
    destination_system: str = Field(min_length=1, max_length=50)
    customer_id: str = Field(min_length=1, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    items: list[OrderItem] = Field(min_length=1)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRouteRequest(BaseModel):
    integration_name: str | None = Field(default=None, max_length=50)
    transport_reference: str | None = None
    process_async: bool = True


class OrderEventRecord(BaseModel):
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class OrderRecord(BaseModel):
    id: UUID
    external_order_id: str
    source_system: str
    destination_system: str
    customer_id: str
    currency: str
    items: list[OrderItem]
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: OrderStatus
    total_amount: Decimal
    integration_name: str | None = None
    transport_reference: str | None = None
    delivery_attempts: int = 0
    last_error: str | None = None
    events: list[OrderEventRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RoutingRuleRecord(BaseModel):
    id: int
    name: str
    priority: int
    source_system: str | None
    destination_system: str | None
    min_total: Decimal | None
    integration_name: str
    is_active: bool


class MetricsRecord(BaseModel):
    total_orders: int
    synced_orders: int
    failed_orders: int
    queued_orders: int
    success_rate: float
    gross_value: Decimal
    by_status: dict[str, int]
    by_integration: dict[str, int]
