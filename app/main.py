from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.schemas.order import OrderCreateRequest, OrderRecord, OrderRouteRequest
from app.services.order_flow import (
    IntegrationNotFoundError,
    InvalidOrderStateError,
    OrderFlowService,
    OrderNotFoundError,
)


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Order routing and synchronization service.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.orderflow = OrderFlowService(settings)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", **app.state.orderflow.health_snapshot()}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready", "mode": settings.environment}

    @app.get("/v1/integrations")
    def list_integrations() -> list[dict[str, object]]:
        return [profile.__dict__.copy() for profile in app.state.orderflow.list_integrations()]

    @app.get("/v1/orders", response_model=list[OrderRecord])
    def list_orders() -> list[OrderRecord]:
        return app.state.orderflow.list_orders()

    @app.post("/v1/orders", response_model=OrderRecord, status_code=status.HTTP_201_CREATED)
    def create_order(payload: OrderCreateRequest) -> OrderRecord:
        return app.state.orderflow.create_order(payload)

    @app.get("/v1/orders/{order_id}", response_model=OrderRecord)
    def get_order(order_id: str) -> OrderRecord:
        try:
            return app.state.orderflow.get_order(_parse_uuid(order_id))
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @app.post("/v1/orders/{order_id}/route", response_model=OrderRecord)
    def route_order(order_id: str, payload: OrderRouteRequest) -> OrderRecord:
        try:
            return app.state.orderflow.route_order(_parse_uuid(order_id), payload)
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except IntegrationNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except InvalidOrderStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @app.post("/v1/orders/{order_id}/sync", response_model=OrderRecord)
    def sync_order(order_id: str, payload: dict[str, str | None] | None = None) -> OrderRecord:
        try:
            transport_reference = None if not payload else payload.get("transport_reference")
            return app.state.orderflow.mark_synced(_parse_uuid(order_id), transport_reference)
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except InvalidOrderStateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return app


def _parse_uuid(raw_value: str):
    from uuid import UUID

    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid order_id.") from exc


app = build_app()
