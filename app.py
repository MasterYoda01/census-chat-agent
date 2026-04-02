"""
Streamlit chat interface for the US Census Chat Agent.
"""

import streamlit as st
from agent.pipeline import run_agent


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="US Census Chat Agent",
    page_icon="📊",
    layout="centered",
)

st.title("📊 US Census Chat Agent")
st.caption(
    "Ask me questions about US population, demographics, income, housing, education, "
    "and more. Powered by the ACS 2020 5-year estimates."
)


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
    st.markdown("**Try asking:**")
    example_questions = [
        "What is the population of California?",
        "Which state has the highest median household income?",
        "Compare poverty rates between Texas and New York",
        "What percentage of people in Florida are over 65?",
        "How many veterans live in each state?",
    ]
    cols = st.columns(1)
    for question in example_questions:
        if st.button(question, key=f"example_{question}", use_container_width=True):
            st.session_state.pending_question = question
            st.rerun()


# ---------------------------------------------------------------------------
# Display existing messages
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Show SQL queries in an expander if present
        if msg.get("sql_queries"):
            with st.expander("🔍 SQL Queries Executed"):
                for i, query in enumerate(msg["sql_queries"]):
                    if query.get("explanation"):
                        st.markdown(f"**{query['explanation']}**")
                    st.code(query["sql"], language="sql")


# ---------------------------------------------------------------------------
# Handle input
# ---------------------------------------------------------------------------

# Check for pending question from example buttons
user_input = None
if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

# Chat input
chat_input = st.chat_input("Ask a question about US census data...")
if chat_input:
    user_input = chat_input

if user_input:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Querying census data..."):
            result = run_agent(
                conversation_history=st.session_state.conversation_history,
                user_message=user_input,
            )

        st.markdown(result["response"])

        # Show SQL queries
        if result["sql_queries"]:
            with st.expander("🔍 SQL Queries Executed"):
                for i, query in enumerate(result["sql_queries"]):
                    if query.get("explanation"):
                        st.markdown(f"**{query['explanation']}**")
                    st.code(query["sql"], language="sql")

    # Update conversation history for multi-turn context
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_input}
    )
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": result["response"]}
    )

    # Store full message with SQL queries for display
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["response"],
        "sql_queries": result["sql_queries"],
    })

    st.rerun()
