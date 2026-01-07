"""
API routes for property search functionality.
"""

import logging
from typing import Annotated, Any, Dict, NamedTuple

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.models.property import PropertyCriteria, SearchRequest, SearchResponse
from app.services.claude_service import ClaudeService, get_claude_service
from app.services.patma_service import PatmaService, get_patma_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


class Services(NamedTuple):
    """Container for injected services."""

    claude: ClaudeService
    patma: PatmaService


def get_services(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Services:
    """Dependency that provides all required services."""
    return Services(
        claude=get_claude_service(settings),
        patma=get_patma_service(settings),
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search for properties",
    description="Parse natural language property requirements and search for matching properties.",
)
async def search_properties(
    request: SearchRequest,
    services: Annotated[Services, Depends(get_services)],
) -> SearchResponse:
    """
    Search for properties based on natural language description.

    This endpoint:
    1. Takes a natural language query describing desired property features
    2. Uses Claude to extract structured search criteria
    3. Searches Patma API for matching properties
    4. Returns filtered and sorted results

    Args:
        request: Search request containing the natural language query.
        services: Injected services for criteria extraction and property search.

    Returns:
        SearchResponse with extracted criteria and matching properties.

    Raises:
        HTTPException: If criteria extraction or property search fails.
    """
    logger.info("Received search request: %s", request.query[:100])

    try:
        # Step 1: Extract structured criteria from natural language
        criteria = await services.claude.extract_criteria(request.query)
        logger.info("Extracted criteria: %s", criteria.model_dump())

        # Step 2: Search for properties using Patma API
        properties = await services.patma.search_properties(
            criteria=criteria,
            max_results=50,
        )
        logger.info("Found %d matching properties", len(properties))

        # Step 3: Build response message
        if properties:
            message = f"Found {len(properties)} properties matching your criteria."
        elif not criteria.locations:
            message = "Please specify a location to search for properties."
        else:
            message = (
                "No properties found matching your exact criteria. "
                "Try broadening your search or adjusting your requirements."
            )

        return SearchResponse(
            criteria=criteria,
            properties=properties,
            total_count=len(properties),
            message=message,
        )

    except ValueError as e:
        logger.error("Failed to extract criteria: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not understand the property requirements: {e}",
        ) from e

    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error: %s", e.message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Claude API error: {e.message}",
        ) from e

    except anthropic.APIConnectionError as e:
        logger.error("Failed to connect to Anthropic API: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Claude API. Please try again later.",
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error("Patma API error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Property search API error: {e.response.status_code}",
        ) from e

    except httpx.RequestError as e:
        logger.error("Failed to connect to Patma API: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to property search API. Please try again later.",
        ) from e

    except Exception as e:
        logger.exception("Unexpected error during search")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {type(e).__name__}: {e}",
        ) from e


@router.post(
    "/extract-criteria",
    response_model=PropertyCriteria,
    summary="Extract search criteria only",
    description="Extract structured criteria from natural language without searching.",
)
async def extract_criteria(
    request: SearchRequest,
    services: Annotated[Services, Depends(get_services)],
) -> PropertyCriteria:
    """
    Extract property criteria from natural language without searching.

    Useful for debugging or previewing what criteria will be extracted
    before running a full search.

    Args:
        request: Search request containing the natural language query.
        services: Injected services.

    Returns:
        PropertyCriteria with the extracted search parameters.
    """
    try:
        return await services.claude.extract_criteria(request.query)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except anthropic.APIStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Claude API error: {e.message}",
        ) from e


@router.get(
    "/sold-prices/{location}",
    response_model=Dict[str, Any],
    summary="Get sold price data for a location",
    description="Get historical sold price statistics for a given location.",
)
async def get_sold_prices(
    location: str,
    services: Annotated[Services, Depends(get_services)],
    property_type: str = "house",
    bedrooms: int = None,
    max_age_months: int = 24,
) -> Dict[str, Any]:
    """
    Get sold price statistics for a location.

    Uses Patma's sold prices endpoint to get historical price data.

    Args:
        location: Postcode.
        services: Injected services.
        property_type: Property type (house, flat, etc.). Required.
        bedrooms: Optional filter by bedroom count.
        max_age_months: How far back to look (default: 24 months).

    Returns:
        Dictionary with sold price statistics.
    """
    try:
        stats = await services.patma.get_sold_prices(
            location=location,
            property_type=property_type,
            bedrooms=bedrooms,
            max_age_months=max_age_months,
        )

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No price data found for location: {location}",
            )

        return stats

    except httpx.HTTPStatusError as e:
        logger.error("Patma API error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Property data API error: {e.response.status_code}",
        ) from e


@router.get(
    "/price-history/{location}",
    response_model=Dict[str, Any],
    summary="Get price history for a location",
    description="Get historical price trends (UKHPI data) for a location.",
)
async def get_price_history(
    location: str,
    services: Annotated[Services, Depends(get_services)],
    property_type: str = None,
) -> Dict[str, Any]:
    """
    Get price history trends for a location.

    Uses UK House Price Index (UKHPI) data to show monthly average prices
    and 12-month percentage changes.

    Args:
        location: Postcode (required).
        services: Injected services.
        property_type: Optional filter by property type.

    Returns:
        Dictionary with monthly price history and trends.
    """
    try:
        history = await services.patma.get_price_history(
            location=location,
            property_type=property_type,
        )

        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No price history found for location: {location}",
            )

        return history

    except httpx.HTTPStatusError as e:
        logger.error("Patma API error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Property data API error: {e.response.status_code}",
        ) from e


@router.get(
    "/local-insights/{location}",
    response_model=Dict[str, Any],
    summary="Get local area insights",
    description="Get local area data including schools, crime rates, and demographics.",
)
async def get_local_insights(
    location: str,
    services: Annotated[Services, Depends(get_services)],
) -> Dict[str, Any]:
    """
    Get local area insights for a location.

    Aggregates data from multiple Patma endpoints:
    - Schools (with Ofsted ratings)
    - Crime statistics
    - Demographics (census data)

    Args:
        location: Postcode for the area.
        services: Injected services.

    Returns:
        Dictionary with combined local insights data.
    """
    try:
        insights = await services.patma.get_local_insights(location=location)

        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No local data found for location: {location}",
            )

        return insights

    except httpx.HTTPStatusError as e:
        logger.error("Patma API error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Property data API error: {e.response.status_code}",
        ) from e
