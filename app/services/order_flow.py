from __future__ import annotations

from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.database import SessionLocal
from app.models import OrderEventModel, OrderItemModel, OrderModel, RoutingRuleModel
from app.schemas.order import (
    MetricsRecord,
    OrderCreateRequest,
    OrderEventRecord,
    OrderItem,
    OrderRecord,
    OrderRouteRequest,
    OrderStatus,
    RoutingRuleRecord,
)
from app.services.connectors import CONNECTORS, ConnectorDeliveryError, ConnectorProfile


class OrderFlowError(RuntimeError):
    pass


class OrderNotFoundError(OrderFlowError):
    pass


class IntegrationNotFoundError(OrderFlowError):
    pass


class InvalidOrderStateError(OrderFlowError):
    pass


class DuplicateOrderError(OrderFlowError):
    pass


class OrderFlowService:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def health_snapshot(self) -> dict[str, str]:
        return {"service": self.settings.app_name, "version": self.settings.app_version, "environment": self.settings.environment}

    def list_integrations(self) -> list[ConnectorProfile]:
        profiles = {connector.profile.name: connector.profile for connector in CONNECTORS.values()}
        return list(profiles.values())

    def list_orders(self, limit: int = 100, status: str | None = None) -> list[OrderRecord]:
        with self.session_factory() as session:
            query = select(OrderModel).order_by(OrderModel.created_at.desc()).limit(min(limit, 500))
            if status:
                query = query.where(OrderModel.status == status)
            return [self._to_record(order) for order in session.scalars(query).all()]

    def get_order(self, order_id: UUID | str) -> OrderRecord:
        with self.session_factory() as session:
            return self._to_record(self._get_order(session, str(order_id)))

    def create_order(self, payload: OrderCreateRequest) -> OrderRecord:
        order = OrderModel(
            external_order_id=payload.external_order_id,
            source_system=payload.source_system.lower(),
            destination_system=payload.destination_system.lower(),
            customer_id=payload.customer_id,
            currency=(payload.currency or self.settings.default_currency).upper(),
            total_amount=self._calculate_total(payload.items),
            notes=payload.notes,
            metadata_json=payload.metadata,
            status=OrderStatus.validated.value,
            items=[OrderItemModel(sku=item.sku, quantity=item.quantity, unit_price=item.unit_price) for item in payload.items],
        )
        order.events.extend([
            OrderEventModel(event_type="order.received", message=f"Received from {order.source_system}"),
            OrderEventModel(event_type="order.validated", message=f"Validated {len(order.items)} line item(s)"),
        ])
        with self.session_factory() as session:
            session.add(order)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateOrderError(f"Order {payload.external_order_id} already exists") from exc
            session.refresh(order)
            return self._to_record(order)

    def route_order(self, order_id: UUID | str, payload: OrderRouteRequest) -> OrderRecord:
        with self.session_factory() as session:
            order = self._get_order(session, str(order_id))
            if order.status not in {OrderStatus.validated.value, OrderStatus.failed.value}:
                raise InvalidOrderStateError(f"Order {order.id} is in {order.status} state and cannot be routed")
            integration = payload.integration_name or self._select_integration(session, order)
            if integration not in CONNECTORS:
                raise IntegrationNotFoundError(f"Integration '{integration}' is not registered")
            order.integration_name = integration
            order.transport_reference = payload.transport_reference
            order.status = OrderStatus.routed.value
            order.last_error = None
            order.events.append(OrderEventModel(event_type="order.routed", message=f"Routed to {CONNECTORS[integration].profile.label}"))
            session.commit()
            return self._to_record(order)

    def process_order(self, order_id: UUID | str) -> OrderRecord:
        with self.session_factory() as session:
            order = self._get_order(session, str(order_id))
            if not order.integration_name:
                order.integration_name = self._select_integration(session, order)
            if order.integration_name not in CONNECTORS:
                raise IntegrationNotFoundError(f"Integration '{order.integration_name}' is not registered")
            order.delivery_attempts += 1
            order.events.append(OrderEventModel(event_type="delivery.attempted", message=f"Attempt {order.delivery_attempts} via {order.integration_name}"))
            try:
                reference = CONNECTORS[order.integration_name].send(order)
            except ConnectorDeliveryError as exc:
                order.status = OrderStatus.failed.value
                order.last_error = str(exc)
                order.events.append(OrderEventModel(event_type="delivery.failed", message=str(exc), event_metadata={"attempt": order.delivery_attempts}))
                session.commit()
                raise
            order.status = OrderStatus.synced.value
            order.transport_reference = reference
            order.last_error = None
            order.events.append(OrderEventModel(event_type="order.synced", message=f"Accepted as {reference}"))
            session.commit()
            return self._to_record(order)

    def mark_synced(self, order_id: UUID | str, transport_reference: str | None = None) -> OrderRecord:
        with self.session_factory() as session:
            order = self._get_order(session, str(order_id))
            if order.status not in {OrderStatus.routed.value, OrderStatus.validated.value, OrderStatus.failed.value}:
                raise InvalidOrderStateError(f"Order {order.id} is in {order.status} state and cannot be synced")
            order.status = OrderStatus.synced.value
            order.transport_reference = transport_reference or order.transport_reference
            order.events.append(OrderEventModel(event_type="order.synced", message="Manually marked as synchronized"))
            session.commit()
            return self._to_record(order)

    def retry_order(self, order_id: UUID | str) -> OrderRecord:
        with self.session_factory() as session:
            order = self._get_order(session, str(order_id))
            if order.status != OrderStatus.failed.value:
                raise InvalidOrderStateError("Only failed orders can be retried")
            order.status = OrderStatus.routed.value
            order.events.append(OrderEventModel(event_type="delivery.retry_queued", message="Manual retry requested"))
            session.commit()
            return self._to_record(order)

    def list_rules(self) -> list[RoutingRuleRecord]:
        with self.session_factory() as session:
            rules = session.scalars(select(RoutingRuleModel).order_by(RoutingRuleModel.priority)).all()
            return [RoutingRuleRecord.model_validate(rule, from_attributes=True) for rule in rules]

    def metrics(self) -> MetricsRecord:
        with self.session_factory() as session:
            rows = session.execute(select(OrderModel.status, func.count(OrderModel.id)).group_by(OrderModel.status)).all()
            by_status = {status: count for status, count in rows}
            integrations = session.execute(select(OrderModel.integration_name, func.count(OrderModel.id)).where(OrderModel.integration_name.is_not(None)).group_by(OrderModel.integration_name)).all()
            total = sum(by_status.values())
            synced = by_status.get(OrderStatus.synced.value, 0)
            gross = session.scalar(select(func.coalesce(func.sum(OrderModel.total_amount), 0))) or Decimal("0")
            return MetricsRecord(
                total_orders=total,
                synced_orders=synced,
                failed_orders=by_status.get(OrderStatus.failed.value, 0),
                queued_orders=by_status.get(OrderStatus.routed.value, 0) + by_status.get(OrderStatus.queued.value, 0),
                success_rate=round((synced / total * 100) if total else 0, 1),
                gross_value=Decimal(gross),
                by_status=by_status,
                by_integration={name: count for name, count in integrations if name},
            )

    def ensure_default_rules(self) -> None:
        defaults = [
            RoutingRuleModel(name="High-value SAP route", priority=10, min_total=Decimal("1000"), integration_name="sap"),
            RoutingRuleModel(name="Shipping fulfillment", priority=20, destination_system="shipping", integration_name="shipstation"),
            RoutingRuleModel(name="Warehouse fulfillment", priority=30, destination_system="wms", integration_name="warehouse"),
            RoutingRuleModel(name="Default ERP route", priority=100, integration_name="netsuite"),
        ]
        with self.session_factory() as session:
            if not session.scalar(select(func.count(RoutingRuleModel.id))):
                session.add_all(defaults)
                session.commit()

    def _select_integration(self, session: Session, order: OrderModel) -> str:
        rules = session.scalars(select(RoutingRuleModel).where(RoutingRuleModel.is_active.is_(True)).order_by(RoutingRuleModel.priority)).all()
        for rule in rules:
            if rule.source_system and rule.source_system != order.source_system:
                continue
            if rule.destination_system and rule.destination_system != order.destination_system:
                continue
            if rule.min_total is not None and order.total_amount < rule.min_total:
                continue
            return rule.integration_name
        return "netsuite"

    @staticmethod
    def _get_order(session: Session, order_id: str) -> OrderModel:
        order = session.get(OrderModel, order_id)
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        return order

    @staticmethod
    def _calculate_total(items: Iterable[OrderItem]) -> Decimal:
        return sum((item.quantity * item.unit_price for item in items), Decimal("0")).quantize(Decimal("0.01"))

    @staticmethod
    def _to_record(order: OrderModel) -> OrderRecord:
        return OrderRecord(
            id=UUID(order.id), external_order_id=order.external_order_id, source_system=order.source_system,
            destination_system=order.destination_system, customer_id=order.customer_id, currency=order.currency,
            total_amount=order.total_amount, status=order.status, integration_name=order.integration_name,
            transport_reference=order.transport_reference, notes=order.notes, metadata=order.metadata_json or {},
            delivery_attempts=order.delivery_attempts, last_error=order.last_error, created_at=order.created_at,
            updated_at=order.updated_at, items=[OrderItem(sku=item.sku, quantity=item.quantity, unit_price=item.unit_price) for item in order.items],
            events=[OrderEventRecord(event_type=event.event_type, message=event.message, metadata=event.event_metadata or {}, created_at=event.created_at) for event in order.events],
        )
