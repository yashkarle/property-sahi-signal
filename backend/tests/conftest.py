import sys
from pathlib import Path

# Add the repo root to Python path so tests can import ingestion module
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Start a Postgres container once per session and create all ORM tables."""
    with PostgresContainer("postgres:15-alpine") as pg:
        sync_url = pg.get_connection_url()
        import app.models  # noqa: F401 — populate Base.metadata
        from app.core.database import Base

        engine = create_engine(sync_url)
        Base.metadata.create_all(engine)
        engine.dispose()

        yield sync_url.replace("postgresql://", "postgresql+asyncpg://")


@pytest.fixture
async def db(postgres_dsn: str) -> AsyncSession:
    """Async DB session for a single test; rolled back after each test."""
    engine = create_async_engine(postgres_dsn)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db: AsyncSession):
    """FastAPI test client with DB dependency overridden to test session."""
    from httpx import ASGITransport, AsyncClient

    from app.dependencies import get_db
    from app.main import app

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
