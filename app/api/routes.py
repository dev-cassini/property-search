"""
API routes for property search functionality.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.models.property import PropertyCriteria, SearchRequest, SearchResponse
from app.services.claude_service import ClaudeService, get_claude_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


def get_services(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClaudeService:
    """Dependency that provides the Claude service."""
    return get_claude_service(settings)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search for properties",
    description="Parse natural language property requirements and search for matching properties.",
)
async def search_properties(
    request: SearchRequest,
    claude_service: Annotated[ClaudeService, Depends(get_services)],
) -> SearchResponse:
    """
    Search for properties based on natural language description.

    This endpoint:
    1. Takes a natural language query describing desired property features
    2. Uses Claude to extract structured search criteria
    3. Returns the extracted criteria (PropertyData integration coming next)

    Args:
        request: Search request containing the natural language query.
        claude_service: Injected Claude service for criteria extraction.

    Returns:
        SearchResponse with extracted criteria and (eventually) matching properties.

    Raises:
        HTTPException: If criteria extraction fails.
    """
    logger.info("Received search request: %s", request.query[:100])

    try:
        # Extract structured criteria from natural language
        criteria = await claude_service.extract_criteria(request.query)

        # For now, return just the extracted criteria
        # PropertyData integration will be added in the next phase
        return SearchResponse(
            criteria=criteria,
            properties=[],
            total_count=0,
            message="Criteria extracted successfully. Property search coming soon!",
        )

    except ValueError as e:
        logger.error("Failed to extract criteria: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not understand the property requirements: {e}",
        ) from e

    except Exception as e:
        logger.exception("Unexpected error during search")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your search.",
        ) from e


@router.post(
    "/extract-criteria",
    response_model=PropertyCriteria,
    summary="Extract search criteria only",
    description="Extract structured criteria from natural language without searching.",
)
async def extract_criteria(
    request: SearchRequest,
    claude_service: Annotated[ClaudeService, Depends(get_services)],
) -> PropertyCriteria:
    """
    Extract property criteria from natural language without searching.

    Useful for debugging or previewing what criteria will be extracted
    before running a full search.

    Args:
        request: Search request containing the natural language query.
        claude_service: Injected Claude service for criteria extraction.

    Returns:
        PropertyCriteria with the extracted search parameters.
    """
    try:
        return await claude_service.extract_criteria(request.query)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
