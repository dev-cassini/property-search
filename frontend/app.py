"""
Property Search Frontend - Streamlit Chat Interface

A chat-style interface for natural language property search,
similar to Claude.ai's conversation UI.
"""

import random
from typing import List, Optional

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"

# Example queries shown on the welcome screen
EXAMPLE_QUERIES: List[str] = [
    "3 bedroom house in Manchester under £400k with a garden",
    "Modern 2-bed flat in London Zone 2, max budget £600k",
    "Family home near good schools in Bristol, 4+ bedrooms",
    "Victorian terraced house in Edinburgh under £350k",
    "Detached property with parking in Leeds, £300-500k",
    "2 bed apartment in Birmingham city centre",
    "Cottage in the Cotswolds with countryside views",
    "New build 3-bed semi in Cardiff under £300k",
]


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "displayed_examples" not in st.session_state:
        # Randomly select 4 examples to display
        st.session_state.displayed_examples = random.sample(EXAMPLE_QUERIES, 4)
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None


def search_properties(query: str) -> dict:
    """
    Call the backend API to search for properties.

    Args:
        query: Natural language property search query.

    Returns:
        API response with criteria and properties.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{API_BASE_URL}/api/search",
                json={"query": query},
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        return {
            "error": "Cannot connect to the API server. Make sure the backend is running with: `uvicorn app.main:app --reload`"
        }
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            error_detail = str(e)
        return {"error": error_detail}
    except Exception as e:
        return {"error": str(e)}


def format_criteria(criteria: dict) -> str:
    """Format extracted criteria as readable markdown."""
    parts = []

    if criteria.get("locations"):
        parts.append(f"**Locations:** {', '.join(criteria['locations'])}")

    bedrooms = []
    if criteria.get("min_bedrooms"):
        bedrooms.append(f"min {criteria['min_bedrooms']}")
    if criteria.get("max_bedrooms"):
        bedrooms.append(f"max {criteria['max_bedrooms']}")
    if bedrooms:
        parts.append(f"**Bedrooms:** {', '.join(bedrooms)}")

    price = []
    if criteria.get("min_price"):
        price.append(f"min £{criteria['min_price']:,}")
    if criteria.get("max_price"):
        price.append(f"max £{criteria['max_price']:,}")
    if price:
        parts.append(f"**Price:** {', '.join(price)}")

    if criteria.get("property_types"):
        parts.append(f"**Property Types:** {', '.join(criteria['property_types'])}")

    if criteria.get("preferences"):
        parts.append(f"**Preferences:** {', '.join(criteria['preferences'])}")

    if criteria.get("deal_breakers"):
        parts.append(f"**Avoid:** {', '.join(criteria['deal_breakers'])}")

    return "\n".join(parts) if parts else "No specific criteria extracted."


def format_property(prop: dict, index: int) -> str:
    """Format a single property as markdown."""
    lines = []

    # Property header with address
    address = prop.get("address", "Unknown Address")
    price = prop.get("price", 0)
    lines.append(f"**{index}. {address}**")
    lines.append(f"💷 £{price:,}")

    # Property details
    details = []
    if prop.get("bedrooms"):
        details.append(f"🛏️ {prop['bedrooms']} bed")
    if prop.get("bathrooms"):
        details.append(f"🛁 {prop['bathrooms']} bath")
    if prop.get("property_type"):
        details.append(f"🏠 {prop['property_type']}")
    if details:
        lines.append(" · ".join(details))

    # Description snippet
    if prop.get("description"):
        desc = prop["description"]
        if len(desc) > 150:
            desc = desc[:150] + "..."
        lines.append(f"\n_{desc}_")

    # Link to listing
    if prop.get("url"):
        lines.append(f"\n[View on portal →]({prop['url']})")

    return "\n".join(lines)


def format_response(data: dict) -> str:
    """Format the full API response as a chat message."""
    if "error" in data:
        return f"❌ **Error:** {data['error']}"

    parts = []

    # Add message
    if data.get("message"):
        parts.append(f"✅ {data['message']}")

    # Add extracted criteria
    if data.get("criteria"):
        parts.append("\n---\n**🔍 Search Criteria Extracted:**\n")
        parts.append(format_criteria(data["criteria"]))

    # Add properties
    properties = data.get("properties", [])
    if properties:
        parts.append(f"\n---\n**🏘️ Properties Found ({len(properties)}):**\n")
        for i, prop in enumerate(properties[:5], 1):  # Show first 5
            parts.append(format_property(prop, i))
            parts.append("")  # Add spacing

        if len(properties) > 5:
            parts.append(f"\n*...and {len(properties) - 5} more properties available*")
    elif data.get("criteria", {}).get("locations"):
        parts.append("\n---\n**No properties found matching your criteria.**")
        parts.append("Try broadening your search or adjusting your requirements.")

    return "\n".join(parts)


def handle_example_click(example: str):
    """Handle when user clicks an example query."""
    st.session_state.pending_query = example


def render_welcome_screen():
    """Render the welcome screen with example queries."""
    # Welcome header
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="font-size: 2.5rem; margin-bottom: 0.5rem;">🏠 Property Search</h1>
            <p style="color: #666; font-size: 1.1rem;">
                Describe your ideal property in plain English and I'll help you find it.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Example queries
    st.markdown("#### Try one of these examples:")

    # Display examples in a 2x2 grid
    col1, col2 = st.columns(2)

    for i, example in enumerate(st.session_state.displayed_examples):
        with col1 if i % 2 == 0 else col2:
            # Truncate long examples for button display
            display_text = example if len(example) <= 45 else example[:42] + "..."
            if st.button(
                f"💬 {display_text}",
                key=f"example_{i}",
                use_container_width=True,
            ):
                handle_example_click(example)
                st.rerun()

    # Shuffle button
    st.markdown("")  # Spacing
    if st.button("🔄 Show different examples", type="secondary"):
        st.session_state.displayed_examples = random.sample(EXAMPLE_QUERIES, 4)
        st.rerun()


def render_chat_history():
    """Render the chat message history."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def process_query(query: str):
    """Process a user query and get response from API."""
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": query})

    # Display user message
    with st.chat_message("user"):
        st.markdown(query)

    # Get and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Searching for properties..."):
            response = search_properties(query)
            formatted = format_response(response)

        st.markdown(formatted)
        st.session_state.messages.append({"role": "assistant", "content": formatted})


def main():
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title="Property Search",
        page_icon="🏠",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Custom CSS
    st.markdown(
        """
        <style>
        /* Hide streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Constrain width */
        .main .block-container {
            max-width: 800px;
            padding-top: 1rem;
        }

        /* Style buttons */
        .stButton > button {
            border-radius: 12px;
            padding: 0.75rem 1rem;
            text-align: left;
            font-size: 0.9rem;
        }

        /* Chat styling */
        .stChatMessage {
            padding: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    init_session_state()

    # Check for pending query from example click
    if st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None
        process_query(query)

    # Render appropriate view
    if not st.session_state.messages:
        render_welcome_screen()
    else:
        render_chat_history()

    # Clear chat button (only show if there are messages)
    if st.session_state.messages:
        if st.button("🗑️ Clear chat", type="secondary"):
            st.session_state.messages = []
            st.session_state.displayed_examples = random.sample(EXAMPLE_QUERIES, 4)
            st.rerun()

    # Chat input (always visible)
    placeholder = random.choice(EXAMPLE_QUERIES)
    if prompt := st.chat_input(f"e.g., {placeholder}"):
        process_query(prompt)
        st.rerun()


if __name__ == "__main__":
    main()
