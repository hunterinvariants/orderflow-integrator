from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from typing import Iterable
from uuid import UUID

from app.core.config import Settings
from app.schemas.order import (
    OrderCreateRequest,
    OrderRecord,
    OrderRouteRequest,
    OrderStatus,
)


@dataclass(frozen=True)
class IntegrationProfile:
    name: str
    description: str
    protocol: str
    is_active: bool = True


class OrderFlowError(RuntimeError):
    pass


class OrderNotFoundError(OrderFlowError):
    pass


class IntegrationNotFoundError(OrderFlowError):
    pass


class InvalidOrderStateError(OrderFlowError):
    pass


class OrderFlowService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = RLock()
        self._orders: dict[UUID, OrderRecord] = {}
        self._integrations: dict[str, IntegrationProfile] = {
            "erp": IntegrationProfile(
                name="erp",
                description="Enterprise resource planning sink for validated orders.",
                protocol="rest",
            ),
            "wms": IntegrationProfile(
                name="wms",
                description="Warehouse management integration used for fulfillment sync.",
                protocol="webhook",
            ),
            "shipping": IntegrationProfile(
                name="shipping",
                description="Carrier handoff integration for shipment creation.",
                protocol="rest",
            ),
            "storefront": IntegrationProfile(
                name="storefront",
                description="Origin system for incoming orders.",
                protocol="event",
            ),
        }

    def health_snapshot(self) -> dict[str, str]:
        return {
            "service": self._settings.app_name,
            "version": self._settings.app_version,
            "environment": self._settings.environment,
        }

    def list_integrations(self) -> list[IntegrationProfile]:
        with self._lock:
            return sorted(self._integrations.values(), key=lambda profile: profile.name)

    def list_orders(self) -> list[OrderRecord]:
        with self._lock:
            return sorted(self._orders.values(), key=lambda order: order.created_at, reverse=True)

    def get_order(self, order_id: UUID) -> OrderRecord:
        with self._lock:
            try:
                return self._orders[order_id]
            except KeyError as exc:
                raise OrderNotFoundError(f"Order {order_id} not found.") from exc

    def create_order(self, payload: OrderCreateRequest) -> OrderRecord:
        currency = payload.currency or self._settings.default_currency
        total_amount = self._calculate_total(payload.items)
        order = OrderRecord(
            external_order_id=payload.external_order_id,
            source_system=payload.source_system,
            destination_system=payload.destination_system,
            customer_id=payload.customer_id,
            currency=currency,
            items=payload.items,
            notes=payload.notes,
            metadata=payload.metadata,
            status=OrderStatus.validated,
            total_amount=total_amount,
            events=[
                f"order-received:{payload.external_order_id}",
                f"order-validated:{payload.source_system}->{payload.destination_system}",
            ],
        )
        with self._lock:
            self._orders[order.id] = order
        return order

    def route_order(self, order_id: UUID, payload: OrderRouteRequest) -> OrderRecord:
        with self._lock:
            order = self._get_mutable_order(order_id)
            integration = self._get_integration(payload.integration_name)
            if order.status not in {OrderStatus.validated, OrderStatus.failed}:
                raise InvalidOrderStateError(
                    f"Order {order_id} is in {order.status} state and cannot be routed."
                )

            order.integration_name = integration.name
            order.transport_reference = payload.transport_reference
            order.status = OrderStatus.routed
            order.events.append(
                f"order-routed:{integration.name}"
                + (f":{payload.transport_reference}" if payload.transport_reference else "")
            )
            order.updated_at = self._now()
            self._orders[order.id] = order
            return order

    def mark_synced(self, order_id: UUID, transport_reference: str | None = None) -> OrderRecord:
        with self._lock:
            order = self._get_mutable_order(order_id)
            if order.status not in {OrderStatus.routed, OrderStatus.validated}:
                raise InvalidOrderStateError(
                    f"Order {order_id} is in {order.status} state and cannot be marked synced."
                )
            if transport_reference:
                order.transport_reference = transport_reference
            order.status = OrderStatus.synced
            order.events.append("order-synced")
            order.updated_at = self._now()
            self._orders[order.id] = order
            return order

    def seed_demo_order(self) -> OrderRecord:
        return self.create_order(
            OrderCreateRequest(
                external_order_id="demo-10001",
                source_system="storefront",
                destination_system="erp",
                customer_id="customer-001",
                currency=self._settings.default_currency,
                items=[
                    {"sku": "SKU-RED-01", "quantity": 2, "unit_price": Decimal("19.95")},
                    {"sku": "SKU-BLUE-02", "quantity": 1, "unit_price": Decimal("42.00")},
                ],
                notes="Seed order for smoke testing.",
                metadata={"seeded": "true"},
            )
        )

    def _get_mutable_order(self, order_id: UUID) -> OrderRecord:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise OrderNotFoundError(f"Order {order_id} not found.") from exc

    def _get_integration(self, integration_name: str) -> IntegrationProfile:
        try:
            return self._integrations[integration_name]
        except KeyError as exc:
            raise IntegrationNotFoundError(
                f"Integration '{integration_name}' is not registered."
            ) from exc

    def _calculate_total(self, items: Iterable) -> Decimal:
        total = Decimal("0")
        for item in items:
            total += item.quantity * item.unit_price
        return total.quantize(Decimal("0.01"))

    def _now(self):
        return datetime.now(timezone.utc)
