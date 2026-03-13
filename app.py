import streamlit as st
import requests
import json

LAMBDA_URL = "https://bjxsf4eivwowufwkrj2mcvmtci0nbagl.lambda-url.ap-south-1.on.aws/"

st.set_page_config(
    page_title="Kerala Police Legal Assistant",
    page_icon="🚔",
    layout="centered"
)

st.markdown("""
<style>
    .source-chip {
        display: inline-block;
        background: #f0f2f6;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        margin: 2px 4px 2px 0;
        color: #444;
        border: 1px solid #ddd;
    }
    .source-chip a {
        text-decoration: none;
        color: #1a73e8;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚔 Kerala Police Legal Assistant")
st.caption("Describe your incident or ask a legal question. The assistant will gather details before searching.")

# --- Session state init ---
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content}
if "sources_log" not in st.session_state:
    st.session_state.sources_log = {}  # turn_index -> list of sources

# --- Render chat history ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Show sources if any were logged for this assistant turn
        if msg["role"] == "assistant" and i in st.session_state.sources_log:
            sources = st.session_state.sources_log[i]
            if sources:
                chips = ""
                for s in sources:
                    url = s.get("url", "")
                    if url:
                        label = url.split("/")[-1] or url
                        chips += f'<span class="source-chip"><a href="{url}" target="_blank">🔗 {label}</a></span>'
                if chips:
                    st.markdown(f"<div style='margin-top:6px'>{chips}</div>", unsafe_allow_html=True)

# --- Chat input ---
user_input = st.chat_input("Type your message...")

if user_input:
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Build history to send (all previous turns, excluding current)
    history_to_send = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    # Append user message to session state
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Stream assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        sources_placeholder = st.empty()

        full_answer = ""
        sources = []

        payload = {
            "action": "answer",
            "query": user_input,
            "messages": history_to_send
        }

        try:
            with requests.post(
                LAMBDA_URL,
                json=payload,
                stream=True,
                timeout=60,
                headers={"Accept": "text/event-stream"}
            ) as resp:
                resp.raise_for_status()

                buffer = ""
                for raw_chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                    buffer += raw_chunk
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        for line in event_str.strip().splitlines():
                            if line.startswith("data: "):
                                data_str = line[len("data: "):]
                                try:
                                    chunk = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                chunk_type = chunk.get("type")

                                if chunk_type == "token":
                                    full_answer += chunk.get("data", "")
                                    response_placeholder.markdown(full_answer + "▌")

                                elif chunk_type == "sources":
                                    sources = chunk.get("data", [])

                                elif chunk_type == "done":
                                    response_placeholder.markdown(full_answer)
                                    # Render source chips
                                    if sources:
                                        chips = ""
                                        for s in sources:
                                            url = s.get("url", "")
                                            if url:
                                                label = url.split("/")[-1] or url
                                                chips += f'<span class="source-chip"><a href="{url}" target="_blank">🔗 {label}</a></span>'
                                        if chips:
                                            sources_placeholder.markdown(
                                                f"<div style='margin-top:6px'>{chips}</div>",
                                                unsafe_allow_html=True
                                            )

                                elif chunk_type == "error":
                                    st.error(chunk.get("data", {}).get("message", "Unknown error"))

        except requests.exceptions.Timeout:
            st.error("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")

    # Save assistant message + sources to session state
    assistant_turn_index = len(st.session_state.messages)
    st.session_state.messages.append({"role": "assistant", "content": full_answer})
    if sources:
        st.session_state.sources_log[assistant_turn_index] = sources

# --- Sidebar: clear conversation ---
with st.sidebar:
    st.header("Conversation")
    st.caption(f"{len(st.session_state.messages)} messages in current session")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.sources_log = {}
        st.rerun()
    st.divider()
    st.caption("Built for Kerala Police RAG Chatbot · Powered by GPT-4o + Qdrant")
