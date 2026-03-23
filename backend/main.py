from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, NewThreadRequest, ThreadTitleRequest
from database import (
    init_db, create_thread, save_message, get_all_threads,
    get_thread_messages, delete_thread, update_thread_title,
    update_thread_timestamp
)
from engine import stream_response
import uuid

app = FastAPI(title="AI Chatbot API", version="1.0.0")

# CORS — Streamlit frontend ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB init on startup
@app.on_event("startup")
def startup():
    init_db()

# ─────────────────────────────────────────
# THREAD ENDPOINTS
# ─────────────────────────────────────────

@app.get("/threads")
def list_threads():
    """Saare threads fetch karo"""
    return get_all_threads()

@app.post("/threads")
def new_thread(req: NewThreadRequest):
    """Naya thread banao"""
    create_thread(req.thread_id, req.title)
    return {"thread_id": req.thread_id, "title": req.title}

@app.patch("/threads/{thread_id}/title")
def rename_thread(thread_id: str, req: ThreadTitleRequest):
    """Thread ka title update karo"""
    update_thread_title(thread_id, req.title)
    return {"message": "Title updated"}

@app.delete("/threads/{thread_id}")
def remove_thread(thread_id: str):
    """Thread delete karo"""
    delete_thread(thread_id)
    return {"message": "Thread deleted"}

@app.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str):
    """Kisi thread ke saare messages fetch karo"""
    return get_thread_messages(thread_id)

# ─────────────────────────────────────────
# CHAT ENDPOINT (SSE Streaming)
# ─────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest):
    """
    User message bhejo, AI ka response stream karo (SSE).
    Message automatically DB mein save hoga.
    """
    # Thread exist nahi karta toh banao
    create_thread(req.thread_id)

    # User message save karo
    save_message(req.thread_id, "user", req.message)

    full_response = []

    def generate():
        for chunk in stream_response(req.thread_id, req.message):
            full_response.append(chunk)
            yield f"data: {chunk}\n\n"

        # Stream khatam — assistant message save karo
        ai_text = "".join(full_response)
        if ai_text.strip():
            save_message(req.thread_id, "assistant", ai_text)
            update_thread_timestamp(req.thread_id)

            # Pehle message hai toh title auto-set karo
            msgs = get_thread_messages(req.thread_id)
            if len(msgs) <= 2:  # sirf user + assistant ka pehla pair
                title = req.message[:50] + ("..." if len(req.message) > 50 else "")
                update_thread_title(req.thread_id, title)

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "AI Chatbot API is running 🚀"}
