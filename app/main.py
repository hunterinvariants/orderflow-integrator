from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.database import SessionLocal, create_schema
from app.schemas.order import MetricsRecord, OrderCreateRequest, OrderRecord, OrderRouteRequest, RoutingRuleRecord
from app.seed import seed_demo_data
from app.services.imports import parse_order_csv
from app.services.order_flow import (
    DuplicateOrderError,
    IntegrationNotFoundError,
    InvalidOrderStateError,
    OrderFlowService,
    OrderNotFoundError,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def build_app(settings: Settings | None = None, session_factory: sessionmaker[Session] = SessionLocal) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        create_schema()
        application.state.orderflow.ensure_default_rules()
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Order integration control tower with durable workflows, routing rules, retries, and audit history.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.parsed_cors_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    app.state.orderflow = OrderFlowService(settings, session_factory)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request):
        return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "orders": app.state.orderflow.list_orders(50),
            "metrics": app.state.orderflow.metrics(),
            "integrations": app.state.orderflow.list_integrations(),
            "rules": app.state.orderflow.list_rules(),
            "version": settings.app_version,
        })

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", **app.state.orderflow.health_snapshot()}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        try:
            with session_factory() as session:
                session.execute(text("SELECT 1"))
            return {"status": "ready", "database": "connected", "mode": settings.environment}
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc

    @app.get("/v1/metrics", response_model=MetricsRecord)
    def metrics() -> MetricsRecord:
        return app.state.orderflow.metrics()

    @app.get("/v1/integrations")
    def list_integrations() -> list[dict[str, object]]:
        return [asdict(profile) for profile in app.state.orderflow.list_integrations()]

    @app.get("/v1/routing-rules", response_model=list[RoutingRuleRecord])
    def list_rules() -> list[RoutingRuleRecord]:
        return app.state.orderflow.list_rules()

    @app.get("/v1/orders", response_model=list[OrderRecord])
    def list_orders(limit: int = 100, order_status: str | None = None) -> list[OrderRecord]:
        return app.state.orderflow.list_orders(limit, order_status)

    @app.post("/v1/orders", response_model=OrderRecord, status_code=status.HTTP_201_CREATED)
    def create_order(payload: OrderCreateRequest) -> OrderRecord:
        try:
            return app.state.orderflow.create_order(payload)
        except DuplicateOrderError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/webhooks/orders", response_model=OrderRecord, status_code=status.HTTP_202_ACCEPTED)
    def ingest_webhook(payload: OrderCreateRequest, x_api_key: str = Header(default="")) -> OrderRecord:
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        order = create_order(payload)
        routed = app.state.orderflow.route_order(order.id, OrderRouteRequest())
        _enqueue_if_available(settings, str(routed.id))
        return routed

    @app.post("/v1/orders/import", status_code=status.HTTP_201_CREATED)
    async def import_orders(file: UploadFile = File(...)) -> dict[str, object]:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=415, detail="Upload a CSV file")
        try:
            payloads = parse_order_csv(await file.read())
            created = [app.state.orderflow.create_order(payload) for payload in payloads]
        except (ValueError, DuplicateOrderError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"created": len(created), "order_ids": [str(order.id) for order in created]}

    @app.get("/v1/orders/{order_id}", response_model=OrderRecord)
    def get_order(order_id: str) -> OrderRecord:
        try:
            return app.state.orderflow.get_order(_parse_uuid(order_id))
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/orders/{order_id}/route", response_model=OrderRecord)
    def route_order(order_id: str, payload: OrderRouteRequest) -> OrderRecord:
        try:
            order = app.state.orderflow.route_order(_parse_uuid(order_id), payload)
            if payload.process_async:
                _enqueue_if_available(settings, str(order.id))
            return order
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except IntegrationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidOrderStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/orders/{order_id}/retry", response_model=OrderRecord)
    def retry_order(order_id: str) -> OrderRecord:
        try:
            order = app.state.orderflow.retry_order(_parse_uuid(order_id))
            _enqueue_if_available(settings, str(order.id))
            return order
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidOrderStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/orders/{order_id}/sync", response_model=OrderRecord)
    def sync_order(order_id: str, payload: dict[str, str | None] | None = None) -> OrderRecord:
        try:
            reference = None if not payload else payload.get("transport_reference")
            return app.state.orderflow.mark_synced(_parse_uuid(order_id), reference)
        except OrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidOrderStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/v1/demo/seed")
    def seed_demo() -> dict[str, object]:
        seeded = seed_demo_data(app.state.orderflow)
        return {"seeded": len(seeded), "external_order_ids": seeded}

    return app


def _enqueue_if_available(settings: Settings, order_id: str) -> None:
    if settings.database_url.startswith("sqlite") and not settings.celery_eager:
        return
    from app.tasks import process_order_task

    process_order_task.delay(order_id)


def _parse_uuid(raw_value: str) -> UUID:
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid order_id") from exc


app = build_app()
