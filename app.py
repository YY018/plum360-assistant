"""Streamlit entry point for Plum 360 Assistant."""

from __future__ import annotations

import os
import sys

import streamlit as st

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.conversation_memory import ConversationMemory
from plum360_assistant.knowledge_domains import KNOWLEDGE_DOMAINS
from plum360_assistant.safety import validate_user_query
from plum360_assistant.service import AssistantUnavailableError, answer_question


def _build_answer(query: str, history: list[dict[str, str]]) -> str:
    """Answer with the LangGraph manual agent and append page citations."""
    result = answer_question(query, history)
    if not result.citations:
        return result.answer
    sources = "\n".join(f"- {citation}" for citation in result.citations)
    return f"{result.answer}\n\n**Sources**\n{sources}"


st.set_page_config(
    page_title="Plum 360 Assistant",
    page_icon="🌙",
    layout="wide",
)

st.title("Plum 360 Assistant")
st.caption("A manual-grounded reference assistant for the Plum 360 infusion pump.")

try:
    load_settings()
except ConfigurationError as exc:
    st.error(f"Configuration error: {exc}")
    st.stop()

st.subheader("Product scope")
st.write(
    "This project is scoped to the Plum 360 System Operating Manual. It does not "
    "connect to a pump, access patient data, or replace clinical training."
)

st.subheader("Knowledge domains")
domain_columns = st.columns(2)
for index, (name, description) in enumerate(KNOWLEDGE_DOMAINS):
    with domain_columns[index % 2]:
        st.markdown(f"**{index + 1}. {name}**")
        st.caption(description)

st.warning(
    "Safety: this software is not a medical device and is not for clinical "
    "decision-making. Never use it to determine medication, dose, rate, or pump "
    "settings. Follow the official manual, facility procedures, and qualified "
    "clinical guidance."
)

settings = load_settings()
is_test_session = (
    os.environ.get("APP_ENV", "").lower() == "testing"
    or "streamlit.testing" in sys.modules
    or os.environ.get("STREAMLIT_TESTING") == "1"
)
chat_enabled = bool(settings.gemini_api_key) and not is_test_session

st.subheader("Ask Plum 360 Assistant")
if chat_enabled:
    st.info(
        "The manual search index is available and the chat can answer based on "
        "the indexed Plum 360 documentation."
    )
else:
    st.info(
        "The chat is ready for manual-grounded answers once GEMINI_API_KEY is "
        "configured, but it is not yet connected to this interface."
    )

st.session_state.setdefault("messages", [])
if "conversation_memory" not in st.session_state:
    st.session_state.conversation_memory = ConversationMemory(max_turns=8)
    st.session_state.conversation_memory.load_from_messages(st.session_state.messages)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input(
    "Ask about the manual or enter a diagnostic query."
    if chat_enabled
    else "Chat responses are not connected yet."
)
if prompt:
    ok, safety_message = validate_user_query(prompt)
    if not ok:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": safety_message})
        st.session_state.conversation_memory.add_user_turn(prompt)
        st.session_state.conversation_memory.add_assistant_turn(safety_message)
        st.rerun()
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": prompt})
    if chat_enabled:
        try:
            with st.spinner("Searching the manual..."):
                assistant_content = _build_answer(prompt, history)
        except AssistantUnavailableError as exc:
            assistant_content = f"⚠️ {exc.message}"
    else:
        assistant_content = (
            "This chat is not connected to the Plum 360 manual search yet. "
            "Use the official manual and qualified clinical guidance for pump "
            "operation."
        )
    st.session_state.messages.append({"role": "assistant", "content": assistant_content})
    st.session_state.conversation_memory.add_user_turn(prompt)
    st.session_state.conversation_memory.add_assistant_turn(assistant_content)
    st.rerun()
