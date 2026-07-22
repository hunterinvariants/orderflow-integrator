from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    external_order_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_system: Mapped[str] = mapped_column(String(50), index=True)
    destination_system: Mapped[str] = mapped_column(String(50), index=True)
    customer_id: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(30), default="validated", index=True)
    integration_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transport_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list[OrderItemModel]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")
    events: Mapped[list[OrderEventModel]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin", order_by="OrderEventModel.created_at")


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    order: Mapped[OrderModel] = relationship(back_populates="items")


class OrderEventModel(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    order: Mapped[OrderModel] = relationship(back_populates="events")


class RoutingRuleModel(Base):
    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    destination_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    min_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    integration_name: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
