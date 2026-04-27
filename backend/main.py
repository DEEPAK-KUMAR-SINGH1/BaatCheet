import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS
from models import ChatRequest, NewThreadRequest, ThreadTitleRequest
from database import (
    init_db, create_thread, save_message,
    get_threads_for_user, get_thread_messages,
    delete_thread, update_thread_title, update_thread_timestamp,
    verify_thread_owner
)
from engine import stream_response, cleanup_chatbot
from auth_routes import router as auth_router, get_current_user
from rag_routes import router as rag_router
from admin_routes import router as admin_router
from auth import increment_chat_count, get_chat_count

# Configure logging to suppress noisy CancelledError during reload
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# LIFESPAN CONTEXT MANAGER
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown lifecycle.
    Ensures clean cleanup of background tasks and DB connections.
    """
    # Startup
    logger.info("Starting up AI Chatbot API...")
    init_db()
    logger.info("Database initialized")

    try:
        yield
    finally:
        # Shutdown - cleanup async tasks
        logger.info("Shutting down gracefully...")
        cleanup_chatbot()
        logger.info("Shutdown complete")


app = FastAPI(title="AI Chatbot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(rag_router)
app.include_router(admin_router)


# ─────────────────────────────────────────
# THREAD ENDPOINTS — all auth-protected, all scoped to current user
# ─────────────────────────────────────────

@app.get("/threads")
def list_threads(current_user=Depends(get_current_user)):
    """Return only the threads that belong to the authenticated user."""
    return get_threads_for_user(current_user["email"])


@app.post("/threads")
def new_thread(req: NewThreadRequest, current_user=Depends(get_current_user)):
    """Create a new thread owned by the authenticated user."""
    create_thread(req.thread_id, user_id=current_user["email"], title=req.title)
    return {"thread_id": req.thread_id, "title": req.title}


@app.patch("/threads/{thread_id}/title")
def rename_thread(thread_id: str, req: ThreadTitleRequest,
                  current_user=Depends(get_current_user)):
    """Rename a thread — only the owner can do this."""
    verify_thread_owner(thread_id, current_user["email"])
    update_thread_title(thread_id, req.title)
    return {"message": "Title updated"}


@app.delete("/threads/{thread_id}")
def remove_thread(thread_id: str, current_user=Depends(get_current_user)):
    """Delete a thread and its messages — only the owner can do this."""
    verify_thread_owner(thread_id, current_user["email"])
    delete_thread(thread_id)
    return {"message": "Thread deleted"}


@app.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str, current_user=Depends(get_current_user)):
    """Return messages for a thread — only visible to the thread owner."""
    verify_thread_owner(thread_id, current_user["email"])
    return get_thread_messages(thread_id)


# ─────────────────────────────────────────
# CHAT ENDPOINT
# ─────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest, current_user=Depends(get_current_user)):
    email = current_user["email"]
    is_approved = current_user["is_approved"]
    is_admin = current_user["is_admin"]

    # 5 chat limit — sirf unapproved non-admin users ke liye
    if not is_approved and not is_admin:
        if get_chat_count(email) >= 5:
            raise HTTPException(
                status_code=403,
                detail="Chat limit reached (5/5). Contact admin for unlimited access."
            )

    # Create thread scoped to this user, then save user message
    create_thread(req.thread_id, user_id=email)
    verify_thread_owner(req.thread_id, email)
    save_message(req.thread_id, "user", req.message)
    increment_chat_count(email)

    def generate():
        full_response = []
        try:
            for chunk in stream_response(req.thread_id, req.message):
                full_response.append(chunk)
                yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"

            ai_text = "".join(full_response)
            if ai_text.strip():
                save_message(req.thread_id, "assistant", ai_text)
                update_thread_timestamp(req.thread_id)
                msgs = get_thread_messages(req.thread_id)
                if len(msgs) <= 2:
                    title = req.message[:50] + ("..." if len(req.message) > 50 else "")
                    update_thread_title(req.thread_id, title)

        except GeneratorExit:
            logger.info(f"Stream closed for thread {req.thread_id[:8]}")
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for thread {req.thread_id[:8]}")
        except Exception as e:
            logger.error(f"Stream error: {type(e).__name__}: {e}")
            yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"
        finally:
            yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ─────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "AI Chatbot API is running"}
