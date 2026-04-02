"""
Streamlit chat interface for the US Census Chat Agent.
"""

import streamlit as st
from agent.pipeline import run_agent_stream


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="US Census Chat Agent",
    page_icon="https://em-content.zobj.net/source/twitter/408/bar-chart_1f4ca.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* ── Import Inter font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ── Global ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Hide default Streamlit chrome ── */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* ── Main container ── */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 800px;
    }

    /* ── Chat messages ── */
    .stChatMessage {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid rgba(59, 130, 246, 0.08);
    }

    /* ── Chat input ── */
    .stChatInput > div {
        border-radius: 12px !important;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
        background-color: #1E293B !important;
        transition: border-color 0.2s ease;
    }
    .stChatInput > div:focus-within {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
    }
    .stChatInput textarea {
        font-family: 'Inter', sans-serif !important;
        color: #E2E8F0 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 10px;
        border: 1px solid rgba(59, 130, 246, 0.2);
        background-color: #1E293B;
        color: #CBD5E1;
        font-family: 'Inter', sans-serif;
        font-size: 0.875rem;
        font-weight: 500;
        padding: 0.625rem 1rem;
        transition: all 0.2s ease;
        text-align: left;
    }
    .stButton > button:hover {
        background-color: rgba(59, 130, 246, 0.1);
        border-color: #3B82F6;
        color: #E2E8F0;
    }

    /* ── Expander (SQL queries) ── */
    .streamlit-expanderHeader {
        border-radius: 10px;
        font-size: 0.8rem;
        font-weight: 500;
        color: #64748B;
    }
    .streamlit-expanderContent {
        border-radius: 0 0 10px 10px;
        border: 1px solid rgba(59, 130, 246, 0.1);
    }

    /* ── Code blocks ── */
    code {
        border-radius: 8px;
    }

    /* ── Spinner ── */
    .stSpinner > div {
        border-color: #3B82F6 !important;
    }

    /* ── Divider ── */
    hr {
        border-color: rgba(59, 130, 246, 0.1);
    }

    /* ── Status badge ── */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        background-color: rgba(59, 130, 246, 0.1);
        color: #60A5FA;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }

    /* ── Header area ── */
    .app-header {
        text-align: center;
        padding: 2.5rem 0 1.25rem 0;
    }
    .app-header .icon-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        margin-bottom: 0.75rem;
    }
    .app-header .icon-box {
        width: 48px;
        height: 48px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    .app-header .icon-box.blue {
        background: linear-gradient(135deg, #1E40AF, #3B82F6);
        box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
    }
    .app-header .icon-box.slate {
        background: linear-gradient(135deg, #1E293B, #334155);
        border: 1px solid rgba(59, 130, 246, 0.15);
    }
    .app-header .icon-connector {
        width: 32px;
        height: 2px;
        background: linear-gradient(90deg, #3B82F6, #475569);
        border-radius: 1px;
    }
    .app-header h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #F1F5F9;
        margin-bottom: 0.1rem;
        letter-spacing: -0.03em;
    }
    .app-header h1 .accent {
        background: linear-gradient(135deg, #60A5FA, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .app-header .tagline {
        font-size: 0.95rem;
        color: #64748B;
        margin-top: 0;
        line-height: 1.6;
    }
    .app-header .tech-pills {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-top: 0.75rem;
        flex-wrap: wrap;
    }
    .app-header .tech-pill {
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        background-color: rgba(30, 41, 59, 0.8);
        color: #94A3B8;
        border: 1px solid rgba(71, 85, 105, 0.3);
    }

    /* ── Pulsing status dot ── */
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #3B82F6;
        animation: pulse 1.5s ease-in-out infinite;
        flex-shrink: 0;
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.4; transform: scale(0.9); }
        50% { opacity: 1; transform: scale(1.1); }
    }

    /* ── Example cards ── */
    .example-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="app-header">
    <div class="icon-row">
        <div class="icon-box blue">&#x1F4CA;</div>
        <div class="icon-connector"></div>
        <div class="icon-box slate">&#x2744;</div>
    </div>
    <h1><span class="accent">Census</span> Chat Agent</h1>
    <p class="tagline">Natural language queries over 242K census block groups.<br>
    Ask about population, income, housing, education, and more.</p>
    <div class="tech-pills">
        <span class="tech-pill">ACS 2020</span>
        <span class="tech-pill">Snowflake</span>
        <span class="tech-pill">Claude Sonnet</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; margin-bottom: 1.25rem;">
    <span class="status-badge">
        <span style="width: 6px; height: 6px; border-radius: 50%; background-color: #34D399; display: inline-block;"></span>
        Live &middot; Snowflake Connected
    </span>
</div>
""", unsafe_allow_html=True)

st.divider()


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []


# ---------------------------------------------------------------------------
# Example questions (shown when chat is empty)
# ---------------------------------------------------------------------------

if not st.session_state.messages:
    st.markdown('<p class="example-label">Try asking</p>', unsafe_allow_html=True)

    example_questions = [
        "What is the population of California?",
        "Which state has the highest median household income?",
        "Compare poverty rates between Texas and New York",
        "What percentage of people in Florida are over 65?",
        "How many veterans live in each state?",
    ]

    cols = st.columns(2)
    for i, question in enumerate(example_questions):
        with cols[i % 2]:
            if st.button(question, key=f"example_{question}", use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()


# ---------------------------------------------------------------------------
# Display existing messages
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sql_queries"):
            with st.expander("View SQL queries"):
                for query in msg["sql_queries"]:
                    if query.get("explanation"):
                        st.caption(query["explanation"])
                    st.code(query["sql"], language="sql")


# ---------------------------------------------------------------------------
# Handle input
# ---------------------------------------------------------------------------

user_input = None
if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

chat_input = st.chat_input("Ask a question about US census data...")
if chat_input:
    user_input = chat_input

if user_input:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Get agent response with streaming
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()

        # Show initial thinking state
        status_placeholder.markdown(
            '<div style="display:flex;align-items:center;gap:8px;color:#64748B;font-size:0.85rem;">'
            '<div class="pulse-dot"></div>Thinking...</div>',
            unsafe_allow_html=True,
        )

        full_response = ""
        sql_queries = []
        had_error = False

        for chunk in run_agent_stream(
            conversation_history=st.session_state.conversation_history,
            user_message=user_input,
        ):
            if chunk["type"] == "status":
                status_placeholder.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;color:#64748B;font-size:0.85rem;">'
                    f'<div class="pulse-dot"></div>{chunk["message"]}</div>',
                    unsafe_allow_html=True,
                )

            elif chunk["type"] == "sql_query":
                sql_queries.append(chunk["query"])

            elif chunk["type"] == "text_delta":
                status_placeholder.empty()
                full_response += chunk["content"]

            elif chunk["type"] == "error":
                status_placeholder.empty()
                full_response = chunk["message"]
                response_placeholder.markdown(full_response)
                had_error = True

            elif chunk["type"] == "done":
                sql_queries = chunk["sql_queries"]

        # Final render without cursor
        status_placeholder.empty()
        response_placeholder.markdown(full_response)

        if sql_queries:
            with st.expander("View SQL queries"):
                for query in sql_queries:
                    if query.get("explanation"):
                        st.caption(query["explanation"])
                    st.code(query["sql"], language="sql")

    # Update conversation history
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_input}
    )
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": full_response}
    )

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "sql_queries": sql_queries,
    })

    st.rerun()
