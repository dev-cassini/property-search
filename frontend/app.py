"""
Property Search Frontend - Streamlit Chat Interface

A chat-style interface for natural language property search,
similar to Claude.ai's conversation UI.
"""

import json
from typing import List

import httpx
import streamlit as st

# Configuration
API_BASE_URL = "http://localhost:8000"

# Example queries that cycle in the placeholder
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
    lines.append(f"£{price:,}")

    # Property details
    details = []
    if prop.get("bedrooms"):
        details.append(f"{prop['bedrooms']} bed")
    if prop.get("bathrooms"):
        details.append(f"{prop['bathrooms']} bath")
    if prop.get("property_type"):
        details.append(prop["property_type"])
    if details:
        lines.append(" | ".join(details))

    # Description snippet
    if prop.get("description"):
        desc = prop["description"]
        if len(desc) > 150:
            desc = desc[:150] + "..."
        lines.append(f"\n_{desc}_")

    # Link to listing
    if prop.get("url"):
        lines.append(f"\n[View on portal]({prop['url']})")

    return "\n".join(lines)


def format_response(data: dict) -> str:
    """Format the full API response as a chat message."""
    if "error" in data:
        return f"**Error:** {data['error']}"

    parts = []

    # Add message
    if data.get("message"):
        parts.append(data["message"])

    # Add extracted criteria
    if data.get("criteria"):
        parts.append("\n---\n**Search Criteria Extracted:**\n")
        parts.append(format_criteria(data["criteria"]))

    # Add properties
    properties = data.get("properties", [])
    if properties:
        parts.append(f"\n---\n**Properties Found ({len(properties)}):**\n")
        for i, prop in enumerate(properties[:5], 1):  # Show first 5
            parts.append(format_property(prop, i))
            parts.append("")  # Add spacing

        if len(properties) > 5:
            parts.append(f"\n*...and {len(properties) - 5} more properties available*")
    elif data.get("criteria", {}).get("locations"):
        parts.append("\n---\n**No properties found matching your criteria.**")
        parts.append("Try broadening your search or adjusting your requirements.")

    return "\n".join(parts)


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


def inject_cycling_placeholder_js():
    """Inject JavaScript to cycle through example placeholders."""
    examples_json = json.dumps(EXAMPLE_QUERIES)

    js_code = f"""
    <script>
    (function() {{
        const examples = {examples_json};
        let currentIndex = 0;
        let lastUpdate = 0;

        function updatePlaceholder(force) {{
            const input = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (input) {{
                const now = Date.now();
                // Only cycle to next example every 3 seconds
                if (force || now - lastUpdate >= 3000) {{
                    input.setAttribute('placeholder', examples[currentIndex]);
                    currentIndex = (currentIndex + 1) % examples.length;
                    lastUpdate = now;
                }} else {{
                    // Keep current placeholder (prevent Streamlit from resetting)
                    const currentPlaceholderIndex = (currentIndex - 1 + examples.length) % examples.length;
                    input.setAttribute('placeholder', examples[currentPlaceholderIndex]);
                }}
            }}
        }}

        // Initial update after short delay
        setTimeout(function() {{ updatePlaceholder(true); }}, 200);

        // Cycle every 3 seconds
        setInterval(function() {{ updatePlaceholder(true); }}, 3000);

        // Aggressively maintain placeholder on any DOM changes
        const observer = new MutationObserver(function(mutations) {{
            updatePlaceholder(false);
        }});

        observer.observe(document.body, {{ childList: true, subtree: true }});

        // Also check frequently to override Streamlit's placeholder
        setInterval(function() {{ updatePlaceholder(false); }}, 100);
    }})();
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)


def main():
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title="Property Search",
        page_icon="🏠",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Custom CSS for centered chat input and styling
    st.markdown(
        """
        <style>
        /* Import Rubik font from Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700&display=swap');

        /* Color palette:
           #CAD2C5 - Light sage green (background)
           #84A98C - Medium sage green (secondary)
           #52796F - Dark teal green (primary/accent)
           #354F52 - Very dark teal (secondary text)
           #2F3E46 - Darkest teal (primary text)
        */

        /* Apply Rubik font globally */
        * {
            font-family: 'Rubik', sans-serif !important;
        }

        /* Hide streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Global background */
        .stApp {
            background-color: #CAD2C5 !important;
        }

        /* Center and constrain content */
        .main .block-container {
            max-width: 800px;
            padding-top: 2rem;
            padding-bottom: 6rem;
        }

        /* Center the chat input container horizontally and vertically */
        .stChatInput {
            max-width: 700px;
            margin: 0 auto;
            position: fixed !important;
            bottom: auto !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            width: 90% !important;
            z-index: 1000;
        }

        /* Style the chat input - reset all nested containers */
        .stChatInput,
        .stChatInput > div,
        .stChatInput > div > div,
        .stChatInput > div > div > div,
        .stChatInput [data-testid] {
            background-color: transparent !important;
            border: none !important;
            border-radius: 24px !important;
            box-shadow: none !important;
        }

        /* Style only the main visible container */
        .stChatInput > div {
            border: 1px solid #84A98C !important;
            box-shadow: 0 2px 8px rgba(47, 62, 70, 0.15) !important;
            background-color: #ffffff !important;
            overflow: hidden !important;
        }

        /* Remove red focus border and style inner elements */
        .stChatInput textarea {
            font-size: 1rem !important;
            background-color: #ffffff !important;
            border: none !important;
            outline: none !important;
            color: #2F3E46 !important;
            border-radius: 24px !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        .stChatInput textarea::placeholder {
            color: #354F52 !important;
            opacity: 0.7;
        }

        .stChatInput textarea:focus {
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }

        /* Fix inner container backgrounds */
        .stChatInput > div > div {
            background-color: transparent !important;
            border: none !important;
        }

        /* Override focus states to remove red border */
        .stChatInput *:focus {
            outline: none !important;
            box-shadow: none !important;
        }

        .stChatInput > div:focus-within {
            border-color: #52796F !important;
            box-shadow: 0 0 0 2px rgba(82, 121, 111, 0.3) !important;
        }

        /* Chat message styling */
        .stChatMessage {
            max-width: 700px;
            margin: 0 auto;
            padding: 1rem;
            background-color: #84A98C !important;
            border-radius: 12px;
        }

        .stChatMessage [data-testid="stMarkdownContainer"] {
            color: #2F3E46 !important;
        }

        /* User message styling */
        [data-testid="stChatMessage"][data-testid*="user"] {
            background-color: #52796F !important;
        }

        [data-testid="stChatMessage"][data-testid*="user"] [data-testid="stMarkdownContainer"] {
            color: #CAD2C5 !important;
        }

        /* Welcome text styling */
        .welcome-container {
            text-align: center;
            padding: 4rem 1rem 2rem 1rem;
            position: fixed;
            top: 35%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 100%;
        }

        .welcome-title {
            font-size: 2.5rem;
            font-weight: 600;
            color: #2F3E46;
            margin-bottom: 0.5rem;
        }

        .welcome-subtitle {
            font-size: 1.1rem;
            color: #354F52;
        }

        /* Clear button styling */
        .stButton > button {
            border-radius: 8px;
            background-color: #52796F !important;
            color: #CAD2C5 !important;
            border: none !important;
        }

        .stButton > button:hover {
            background-color: #354F52 !important;
            color: #CAD2C5 !important;
        }

        /* Links */
        a {
            color: #52796F !important;
        }

        a:hover {
            color: #354F52 !important;
        }

        /* Spinner */
        .stSpinner > div {
            border-top-color: #52796F !important;
        }

        /* When there are messages, move chat input to bottom */
        .has-messages .stChatInput {
            position: fixed !important;
            bottom: 1rem !important;
            top: auto !important;
            transform: translateX(-50%) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    init_session_state()

    # Inject JavaScript for cycling placeholders
    inject_cycling_placeholder_js()

    # Show welcome screen or chat history
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="welcome-container">
                <div class="welcome-title">Property Search</div>
                <div class="welcome-subtitle">
                    Describe your ideal property and I'll help you find it
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Add class to body to indicate we have messages (moves chat input to bottom)
        st.markdown(
            """
            <script>
                document.body.classList.add('has-messages');
                const main = document.querySelector('.main');
                if (main) main.classList.add('has-messages');
            </script>
            <style>
                /* Override: move chat input to bottom when there are messages */
                .stChatInput {
                    position: fixed !important;
                    bottom: 1rem !important;
                    top: auto !important;
                    left: 50% !important;
                    transform: translateX(-50%) !important;
                }
                .welcome-container {
                    display: none;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        render_chat_history()

        # Clear chat button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Clear chat", type="secondary", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

    # Chat input (centered via CSS, placeholder set by JavaScript)
    if prompt := st.chat_input(" "):
        process_query(prompt)
        st.rerun()


if __name__ == "__main__":
    main()
