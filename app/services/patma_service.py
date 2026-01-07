"""
Patma API service for searching UK property listings.

Uses the Patma (patma.co.uk) API to search for properties based on
location and criteria extracted from natural language queries.

API Documentation: https://app.patma.co.uk/api/doc/
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings
from app.models.property import Property, PropertyCriteria

logger = logging.getLogger(__name__)

# Property type mappings for Patma API
PROPERTY_TYPE_MAP = {
    "house": "house",
    "detached": "detached",
    "semi-detached": "semi_detached",
    "semi detached": "semi_detached",
    "terraced": "terraced",
    "terrace": "terraced",
    "flat": "flat",
    "apartment": "flat",
    "bungalow": "bungalow",
    "maisonette": "flat",
}


class PatmaService:
    """Service for interacting with Patma property data API."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the Patma service.

        Args:
            settings: Application settings containing API configuration.
        """
        self.api_key = settings.patma_api_key
        self.base_url = settings.patma_base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def search_properties(
        self,
        criteria: PropertyCriteria,
        max_results: int = 50,
    ) -> List[Property]:
        """
        Search for properties matching the given criteria.

        Uses the /api/prospector/v1/property-listing/ endpoint.

        Args:
            criteria: Extracted search criteria from natural language.
            max_results: Maximum number of results to return.

        Returns:
            List of matching Property objects.
        """
        if not criteria.locations:
            logger.warning("No locations specified in criteria")
            return []

        all_properties: List[Property] = []
        seen_ids: set = set()

        for location in criteria.locations:
            try:
                params = self._build_listing_params(criteria, location, max_results)
                properties = await self._fetch_listings(params)

                for prop in properties:
                    if prop.id not in seen_ids:
                        all_properties.append(prop)
                        seen_ids.add(prop.id)

                        if len(all_properties) >= max_results:
                            break

            except Exception as e:
                logger.error("Error searching properties in %s: %s", location, e)
                continue

            if len(all_properties) >= max_results:
                break

        all_properties.sort(key=lambda p: p.price)
        return all_properties[:max_results]

    def _build_listing_params(
        self,
        criteria: PropertyCriteria,
        location: str,
        max_results: int,
    ) -> Dict[str, Any]:
        """
        Build query parameters for property listing search.

        Args:
            criteria: Property search criteria.
            location: Location to search (postcode).
            max_results: Maximum results to return.

        Returns:
            Dictionary of query parameters.
        """
        params: Dict[str, Any] = {
            "postcode": location,
            "radius": 5,  # 5 mile radius default
            "page_size": min(max_results, 100),
        }

        # Bedroom filters
        if criteria.min_bedrooms is not None:
            params["bedrooms_gte"] = criteria.min_bedrooms
        if criteria.max_bedrooms is not None:
            params["bedrooms_lte"] = criteria.max_bedrooms

        # Price filters
        if criteria.min_price is not None:
            params["price_gte"] = criteria.min_price
        if criteria.max_price is not None:
            params["price_lte"] = criteria.max_price

        # Property type filter
        if criteria.property_types:
            prop_type = criteria.property_types[0].lower()
            mapped_type = PROPERTY_TYPE_MAP.get(prop_type)
            if mapped_type:
                params["property_type"] = mapped_type

        # Check preferences for special filters
        prefs_lower = [p.lower() for p in criteria.preferences]
        if any("no chain" in p for p in prefs_lower):
            params["no_chain"] = True
        if any("refurb" in p or "renovation" in p for p in prefs_lower):
            params["needs_refurb"] = True
        if any("reduced" in p or "discount" in p for p in prefs_lower):
            params["reduced_percent_gte"] = 5

        return params

    async def _fetch_listings(
        self,
        params: Dict[str, Any],
    ) -> List[Property]:
        """
        Fetch property listings from Patma API.

        Args:
            params: Query parameters for the search.

        Returns:
            List of Property objects.
        """
        url = f"{self.base_url}/prospector/v1/property-listing/"
        logger.info("Fetching listings from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # Handle paginated response
        results = data.get("results", [])
        if isinstance(data, list):
            results = data

        return self._parse_listings(results)

    async def get_asking_prices(
        self,
        location: str,
        bedrooms: int,
        property_type: str = "house",
    ) -> Dict[str, Any]:
        """
        Get asking price statistics for a location.

        Uses /api/prospector/v1/asking-prices/ endpoint.

        Args:
            location: Postcode.
            bedrooms: Number of bedrooms (required by API).
            property_type: Property type (required by API).

        Returns:
            Dictionary with asking price statistics.
        """
        params = {
            "postcode": location,
            "bedrooms": bedrooms,
            "property_type": PROPERTY_TYPE_MAP.get(property_type.lower(), property_type),
        }

        url = f"{self.base_url}/prospector/v1/asking-prices/"
        logger.info("Getting asking prices from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_sold_prices(
        self,
        location: str,
        property_type: str = "house",
        max_age_months: int = 24,
        bedrooms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get sold price statistics for a location.

        Uses /api/prospector/v1/sold-prices/ endpoint.

        Args:
            location: Postcode.
            property_type: Property type (required by API).
            max_age_months: How far back to look (default 24 months).
            bedrooms: Optional bedroom filter.

        Returns:
            Dictionary with sold price statistics.
        """
        params: Dict[str, Any] = {
            "postcode": location,
            "property_type": PROPERTY_TYPE_MAP.get(property_type.lower(), property_type),
            "max_age_months": max_age_months,
        }

        if bedrooms is not None:
            params["bedrooms"] = bedrooms

        url = f"{self.base_url}/prospector/v1/sold-prices/"
        logger.info("Getting sold prices from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_price_history(
        self,
        location: str,
        property_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get historical price trends (UKHPI data).

        Uses /api/prospector/v1/price-history/ endpoint.

        Args:
            location: Postcode (required).
            property_type: Optional property type filter.

        Returns:
            Dictionary with monthly price history and trends.
        """
        params: Dict[str, Any] = {"postcode": location}

        if property_type:
            params["property_type"] = PROPERTY_TYPE_MAP.get(
                property_type.lower(), property_type
            )

        url = f"{self.base_url}/prospector/v1/price-history/"
        logger.info("Getting price history from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_schools(
        self,
        location: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Get nearby schools with Ofsted ratings.

        Uses /api/prospector/v1/schools/ endpoint.

        Args:
            location: Postcode.
            max_results: Maximum number of schools to return.

        Returns:
            Dictionary with school information.
        """
        params = {
            "postcode": location,
            "max_results": max_results,
        }

        url = f"{self.base_url}/prospector/v1/schools/"
        logger.info("Getting schools from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_crime_data(
        self,
        location: str,
    ) -> Dict[str, Any]:
        """
        Get crime statistics for a location.

        Uses /api/prospector/v1/crime/ endpoint.

        Args:
            location: Postcode.

        Returns:
            Dictionary with crime rating and statistics.
        """
        params = {"postcode": location}

        url = f"{self.base_url}/prospector/v1/crime/"
        logger.info("Getting crime data from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_demographics(
        self,
        location: str,
    ) -> Dict[str, Any]:
        """
        Get demographic data for a location.

        Uses /api/prospector/v2/demographics/ endpoint.

        Args:
            location: Postcode.

        Returns:
            Dictionary with demographic statistics.
        """
        params = {"postcode": location}

        url = f"{self.base_url}/prospector/v2/demographics/"
        logger.info("Getting demographics from Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def get_local_insights(
        self,
        location: str,
    ) -> Dict[str, Any]:
        """
        Get combined local insights (schools, crime, demographics).

        Aggregates data from multiple endpoints.

        Args:
            location: Postcode.

        Returns:
            Dictionary with combined local insights.
        """
        insights: Dict[str, Any] = {"postcode": location}

        # Fetch all insights in parallel would be better, but for simplicity:
        try:
            insights["schools"] = await self.get_schools(location)
        except Exception as e:
            logger.warning("Failed to get schools: %s", e)
            insights["schools"] = None

        try:
            insights["crime"] = await self.get_crime_data(location)
        except Exception as e:
            logger.warning("Failed to get crime data: %s", e)
            insights["crime"] = None

        try:
            insights["demographics"] = await self.get_demographics(location)
        except Exception as e:
            logger.warning("Failed to get demographics: %s", e)
            insights["demographics"] = None

        return insights

    async def calculate_stamp_duty(
        self,
        value: int,
        country: str = "england",
    ) -> Dict[str, Any]:
        """
        Calculate stamp duty for a property purchase.

        Uses /api/prospector/v1/stamp-duty/ endpoint.

        Args:
            value: Property value in GBP.
            country: Country (england, wales, scotland).

        Returns:
            Dictionary with stamp duty calculations.
        """
        params = {
            "value": value,
            "country": country,
        }

        url = f"{self.base_url}/prospector/v1/stamp-duty/"
        logger.info("Calculating stamp duty via Patma: %s", url)

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def _parse_listings(self, results: List[Dict]) -> List[Property]:
        """
        Parse Patma API listing response into Property objects.

        Args:
            results: List of listing dictionaries from API.

        Returns:
            List of Property objects.
        """
        properties = []

        for item in results:
            try:
                # Extract price - could be in different fields
                price = (
                    item.get("price")
                    or item.get("asking_price")
                    or item.get("current_price")
                    or 0
                )
                if isinstance(price, str):
                    price = int(price.replace(",", "").replace("£", ""))

                prop = Property(
                    id=str(item.get("id", item.get("portal_id", ""))),
                    address=item.get("address", item.get("full_address", "Unknown")),
                    price=int(price),
                    bedrooms=item.get("bedrooms"),
                    bathrooms=item.get("bathrooms"),
                    property_type=item.get("property_type", item.get("type")),
                    description=item.get("description", item.get("summary")),
                    url=item.get("portal_url", item.get("url", item.get("link"))),
                    image_url=item.get("image_url", item.get("main_image")),
                    latitude=item.get("latitude", item.get("lat")),
                    longitude=item.get("longitude", item.get("lng")),
                )
                properties.append(prop)

            except Exception as e:
                logger.warning("Failed to parse listing: %s - %s", e, item)
                continue

        return properties


# Dependency injection helper
_patma_service: Optional[PatmaService] = None


def get_patma_service(settings: Settings) -> PatmaService:
    """
    Get or create the Patma service singleton.
    """
    global _patma_service
    if _patma_service is None:
        _patma_service = PatmaService(settings)
    return _patma_service
