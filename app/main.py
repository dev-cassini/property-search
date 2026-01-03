"""
Property Search API - FastAPI application entry point.

A property recommendation service that uses Claude to parse natural language
property requirements and searches PropertyData.co.uk for matching listings.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the application.
    Currently validates that required settings are available.
    """
    settings = get_settings()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    # Validate API keys are present (will raise if missing)
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    if not settings.propertydata_api_key:
        raise RuntimeError("PROPERTYDATA_API_KEY is required")

    logger.info("Configuration validated successfully")
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "A property recommendation API that uses AI to parse natural language "
            "property requirements and find matching UK property listings."
        ),
        lifespan=lifespan,
    )

    # Configure CORS for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    return app


# Create the application instance
app = create_app()


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns basic application status for monitoring and load balancers.
    """
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
