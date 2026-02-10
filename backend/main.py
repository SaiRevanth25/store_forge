"""
Main module for Mindmap API.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from core.database import db_manager

from api.user_routes import router as user_router
from api.store_routes import router as store_router


import logging

logger = logging.getLogger(__name__)


async def startup_event():
    """Initialize resources on startup."""
    logger.info("Initializing application resources...")

    # Startup: Initialize database
    await db_manager.initialize()


async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down application...")

    await db_manager.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    # Startup event
    await startup_event()

    yield

    # Shutdown event
    await shutdown_event()


app = FastAPI(title="store_forge", lifespan=lifespan)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# Include API routers
app.include_router(user_router, prefix="/api", tags=["users"])
app.include_router(store_router, prefix="/api", tags=["stores"])



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
