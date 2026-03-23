import streamlit as st
import requests
import uuid

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="AI Assistant",
    page_icon="🤖",
    layout="wide"
)

# ─────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────

def api_get_threads():
    try:
        res = requests.get(f"{API_BASE}/threads", timeout=5)
        return res.json() if res.ok else []
    except:
        st.error("❌ Backend se connect nahi ho pa raha. `uvicorn main:app` chala rahe ho?")
        return []

def api_new_thread(thread_id: str):
    try:
        requests.post(f"{API_BASE}/threads", json={"thread_id": thread_id}, timeout=5)
    except:
        pass

def api_get_messages(thread_id: str):
    try:
        res = requests.get(f"{API_BASE}/threads/{thread_id}/messages", timeout=5)
        return res.json() if res.ok else []
    except:
        return []

def api_delete_thread(thread_id: str):
    try:
        requests.delete(f"{API_BASE}/threads/{thread_id}", timeout=5)
    except:
        pass

def api_rename_thread(thread_id: str, title: str):
    try:
        requests.patch(f"{API_BASE}/threads/{thread_id}/title", json={"title": title}, timeout=5)
    except:
        pass

def api_chat_stream(thread_id: str, message: str):
    """SSE stream se AI response yield karo"""
    try:
        with requests.post(
            f"{API_BASE}/chat",
            json={"thread_id": thread_id, "message": message},
            stream=True,
            timeout=60
        ) as res:
            for line in res.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        chunk = decoded[6:]
                        if chunk == "[DONE]":
                            break
                        yield chunk
    except Exception as e:
        yield f"\n\n❌ Error: {str(e)}"

# ─────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())
    api_new_thread(st.session_state["thread_id"])

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "threads" not in st.session_state:
    st.session_state["threads"] = api_get_threads()

if "rename_mode" not in st.session_state:
    st.session_state["rename_mode"] = None

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────

st.sidebar.title("🤖 AI Assistant")
st.sidebar.caption("Powered by Mistral + LangGraph + FastAPI")
st.sidebar.divider()

if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
    new_id = str(uuid.uuid4())
    st.session_state["thread_id"] = new_id
    st.session_state["message_history"] = []
    api_new_thread(new_id)
    st.session_state["threads"] = api_get_threads()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("💬 Past Conversations")

threads = st.session_state["threads"]

for thread in threads:
    tid = thread["thread_id"]
    title = thread.get("title", "New Chat")
    is_active = tid == st.session_state["thread_id"]
    label = ("▶ " if is_active else "") + title

    col1, col2, col3 = st.sidebar.columns([6, 1, 1])

    with col1:
        if st.button(label, key=f"load_{tid}", use_container_width=True):
            st.session_state["thread_id"] = tid
            msgs = api_get_messages(tid)
            st.session_state["message_history"] = [
                {"role": m["role"], "content": m["content"]} for m in msgs
            ]
            st.rerun()

    with col2:
        if st.button("✏️", key=f"rename_{tid}"):
            st.session_state["rename_mode"] = tid

    with col3:
        if st.button("🗑️", key=f"del_{tid}"):
            api_delete_thread(tid)
            if tid == st.session_state["thread_id"]:
                st.session_state["thread_id"] = str(uuid.uuid4())
                st.session_state["message_history"] = []
                api_new_thread(st.session_state["thread_id"])
            st.session_state["threads"] = api_get_threads()
            st.rerun()

    # Rename input
    if st.session_state["rename_mode"] == tid:
        new_title = st.sidebar.text_input("New name:", value=title, key=f"title_input_{tid}")
        if st.sidebar.button("✅ Save", key=f"save_rename_{tid}"):
            api_rename_thread(tid, new_title)
            st.session_state["rename_mode"] = None
            st.session_state["threads"] = api_get_threads()
            st.rerun()

# ─────────────────────────────────────────
# MAIN CHAT AREA
# ─────────────────────────────────────────

st.title("🤖 AI Assistant")

# Chat history display
for msg in st.session_state["message_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Ask me anything...")

if user_input:
    # User message dikhao
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI response stream karo
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        for chunk in api_chat_stream(st.session_state["thread_id"], user_input):
            full_response += chunk
            response_placeholder.markdown(full_response + "▌")

        response_placeholder.markdown(full_response)

    st.session_state["message_history"].append({"role": "assistant", "content": full_response})

    # Threads refresh karo (title update ke liye)
    st.session_state["threads"] = api_get_threads()
