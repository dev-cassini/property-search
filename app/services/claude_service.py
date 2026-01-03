"""
Claude API service for extracting structured property criteria.

Uses the Anthropic SDK to parse natural language property descriptions
into structured PropertyCriteria objects.
"""

import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic

from app.config import Settings
from app.models.property import PropertyCriteria

logger = logging.getLogger(__name__)

# System prompt that instructs Claude how to extract property criteria
EXTRACTION_SYSTEM_PROMPT = """You are a property search assistant that extracts structured search criteria from natural language descriptions.

Your task is to parse the user's property requirements and return a JSON object with the following structure:

{
    "min_bedrooms": <integer or null>,
    "max_bedrooms": <integer or null>,
    "min_price": <integer in GBP or null>,
    "max_price": <integer in GBP or null>,
    "locations": [<list of location strings: cities, towns, areas, postcodes>],
    "property_types": [<list of property types: "house", "flat", "apartment", "bungalow", "terraced", "semi-detached", "detached", "cottage", "maisonette">],
    "preferences": [<list of desired features: "garden", "parking", "garage", "modern kitchen", "ensuite", "good schools", "quiet area", etc.>],
    "deal_breakers": [<list of things to avoid: "no garden", "busy road", "ex-council", etc.>]
}

Guidelines:
- Extract explicit requirements from the text
- Convert price mentions to integers (e.g., "£400k" = 400000, "half a million" = 500000)
- Normalize location names (e.g., "Greater Manchester" is fine, but also extract specific areas if mentioned)
- Be liberal with preferences - include anything that sounds like a desired feature
- Only include deal_breakers for things explicitly mentioned as unwanted
- If something isn't mentioned, use null for numbers or empty list for arrays
- Return ONLY the JSON object, no additional text or explanation"""


class ClaudeService:
    """Service for interacting with Claude API to extract property criteria."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the Claude service.

        Args:
            settings: Application settings containing API configuration.
        """
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    async def extract_criteria(self, query: str) -> PropertyCriteria:
        """
        Extract structured property criteria from natural language query.

        Args:
            query: Natural language description of property requirements.

        Returns:
            PropertyCriteria object with extracted search parameters.

        Raises:
            ValueError: If Claude's response cannot be parsed as valid criteria.
            anthropic.APIError: If the API request fails.
        """
        logger.info("Extracting criteria from query: %s", query[:100])

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Extract property search criteria from this description:\n\n{query}",
                }
            ],
        )

        # Extract the text response
        response_text = message.content[0].text
        logger.debug("Claude response: %s", response_text)

        # Parse the JSON response
        try:
            # Handle potential markdown code blocks in response
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```"):
                # Remove markdown code block formatting
                lines = cleaned_response.split("\n")
                # Remove first line (```json) and last line (```)
                cleaned_response = "\n".join(lines[1:-1])

            criteria_dict = json.loads(cleaned_response)
            criteria = PropertyCriteria.model_validate(criteria_dict)
            logger.info("Successfully extracted criteria: %s", criteria.model_dump())
            return criteria

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            raise ValueError(
                f"Failed to parse property criteria from response: {response_text}"
            ) from e


# Dependency injection helper for FastAPI
_claude_service: Optional[ClaudeService] = None


def get_claude_service(settings: Settings) -> ClaudeService:
    """
    Get or create the Claude service singleton.

    This allows for dependency injection in FastAPI routes while
    maintaining a single client instance.
    """
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService(settings)
    return _claude_service
