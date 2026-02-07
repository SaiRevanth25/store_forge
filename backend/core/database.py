"""Database manager for async SQLAlchemy operations"""

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from core.config import settings

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Manages async database connections using SQLAlchemy"""

    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self._database_url = settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        )

    async def initialize(self) -> None:
        """Initialize async database connection"""
        self.engine = create_async_engine(
            self._database_url,
        )
        
        # Note: Database schema is managed by Alembic migrations
        # Run 'alembic upgrade head' to apply migrations
        logger.info("Database initialized")

    async def close(self) -> None:
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
        logger.info("Database connection closed")

    def get_engine(self) -> AsyncEngine:
        """Get the SQLAlchemy engine for metadata tables"""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        return self.engine


# Global database manager instance
db_manager = DatabaseManager()
