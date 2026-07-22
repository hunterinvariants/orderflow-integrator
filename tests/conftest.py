import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.database import Base
from app.main import build_app


@pytest.fixture
def client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    settings = Settings(database_url="sqlite://", celery_eager=False, environment="test")
    app = build_app(settings=settings, session_factory=testing_session)
    with TestClient(app) as test_client:
        yield test_client
