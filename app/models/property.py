"""
Pydantic models for property search functionality.

These models define the data structures used throughout the application
for API requests, responses, and internal data representation.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class PropertyCriteria(BaseModel):
    """
    Structured search criteria extracted from natural language input.

    This is the output format that Claude produces when parsing
    a user's property search description.
    """

    min_bedrooms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum number of bedrooms required",
    )
    max_bedrooms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum number of bedrooms",
    )
    min_price: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum price in GBP",
    )
    max_price: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum price in GBP",
    )
    locations: List[str] = Field(
        default_factory=list,
        description="List of desired locations (towns, cities, postcodes)",
    )
    property_types: List[str] = Field(
        default_factory=list,
        description="Types of properties (e.g., 'house', 'flat', 'bungalow')",
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="Desired features (e.g., 'garden', 'parking', 'modern kitchen')",
    )
    deal_breakers: List[str] = Field(
        default_factory=list,
        description="Features or conditions to avoid",
    )


class SearchRequest(BaseModel):
    """API request body for property search."""

    query: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language description of desired property",
        examples=[
            "I want a 3-bed house in Manchester under £400k with a garden",
            "Looking for a modern 2-bedroom flat in London Zone 2, max budget £600k",
        ],
    )


class Property(BaseModel):
    """
    Individual property listing from PropertyData API.

    This model represents the key fields we extract from PropertyData
    API responses for display to users.
    """

    id: str = Field(description="Unique property identifier")
    address: str = Field(description="Full property address")
    price: int = Field(ge=0, description="Asking price in GBP")
    bedrooms: Optional[int] = Field(default=None, ge=0, description="Number of bedrooms")
    bathrooms: Optional[int] = Field(default=None, ge=0, description="Number of bathrooms")
    property_type: Optional[str] = Field(default=None, description="Type of property")
    description: Optional[str] = Field(default=None, description="Property description")
    url: Optional[str] = Field(default=None, description="Link to full listing")
    image_url: Optional[str] = Field(default=None, description="Main property image URL")
    latitude: Optional[float] = Field(default=None, description="Property latitude")
    longitude: Optional[float] = Field(default=None, description="Property longitude")


class SearchResponse(BaseModel):
    """API response containing search results."""

    criteria: PropertyCriteria = Field(
        description="Extracted search criteria from the natural language query",
    )
    properties: List[Property] = Field(
        default_factory=list,
        description="List of matching properties",
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total number of matching properties found",
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional message about the search results",
    )
