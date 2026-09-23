import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from Connectors.routes import router as connectors_router
from admin_routes import router as admin_router
from auth import get_chat_count, increment_chat_count
from auth_routes import get_current_user, router as auth_router
from config import CORS_ORIGINS
from database import (
    create_thread,
    delete_messages_after,
    delete_thread,
    get_last_user_message,
    get_thread_messages,
    get_thread_workspace_id,
    get_threads_for_user,
    get_workspace_documents,
    init_db,
    record_event,
    save_message,
    update_thread_timestamp,
    update_thread_title,
    update_thread_workspace,
    verify_thread_owner,
    verify_workspace_owner,
)
from engine import cleanup_chatbot, stream_response
from models import ChatRequest, NewThreadRequest, ThreadTitleRequest
from rag_engine import retrieve_context_with_sources
from rag_routes import router as rag_router
from workspace_routes import router as workspace_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AI Chatbot API...")
    init_db()
    logger.info("Database initialized")
    try:
        yield
    finally:
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
app.include_router(workspace_router)
app.include_router(connectors_router)


@app.get("/threads")
def list_threads(current_user=Depends(get_current_user)):
    return get_threads_for_user(current_user["email"])


@app.post("/threads")
def new_thread(req: NewThreadRequest, current_user=Depends(get_current_user)):
    workspace_id = getattr(req, "workspace_id", None)
    if workspace_id:
        verify_workspace_owner(workspace_id, current_user["email"])
    create_thread(req.thread_id, user_id=current_user["email"], title=req.title, workspace_id=workspace_id)
    return {"thread_id": req.thread_id, "title": req.title, "workspace_id": workspace_id}


@app.patch("/threads/{thread_id}/title")
def rename_thread(thread_id: str, req: ThreadTitleRequest, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    update_thread_title(thread_id, req.title)
    return {"message": "Title updated"}


@app.delete("/threads/{thread_id}")
def remove_thread(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    delete_thread(thread_id)
    return {"message": "Thread deleted"}


@app.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str, current_user=Depends(get_current_user)):
    verify_thread_owner(thread_id, current_user["email"])
    return get_thread_messages(thread_id)


def _check_chat_limit(current_user):
    if not current_user["is_approved"] and not current_user["is_admin"]:
        if get_chat_count(current_user["email"]) >= 5:
            raise HTTPException(
                status_code=403,
                detail="Chat limit reached (5/5). Contact admin for unlimited access.",
            )


def _workspace_context(workspace_id: str | None, message: str, email: str):
    if not workspace_id:
        return "", []
    verify_workspace_owner(workspace_id, email)
    indexed_docs = [
        doc for doc in get_workspace_documents(workspace_id)
        if doc.get("status") == "indexed"
    ]
    if not indexed_docs:
        return "", []
    context, sources = retrieve_context_with_sources(workspace_id, message, k=5)
    return context, sources


def _save_assistant_stream_result(
    thread_id: str,
    user_message: str,
    full_response: list[str],
    sources: list[dict],
    workspace_id: str | None,
    status: str,
):
    ai_text = "".join(full_response)
    if not ai_text.strip():
        return
    save_message(
        thread_id,
        "assistant",
        ai_text,
        metadata={"sources": sources, "workspace_id": workspace_id},
        status=status,
    )
    update_thread_timestamp(thread_id)
    msgs = get_thread_messages(thread_id)
    if len(msgs) <= 2:
        title = user_message[:50] + ("..." if len(user_message) > 50 else "")
        update_thread_title(thread_id, title)


@app.post("/chat")
def chat(req: ChatRequest, current_user=Depends(get_current_user)):
    email = current_user["email"]
    _check_chat_limit(current_user)

    workspace_id = req.workspace_id
    if workspace_id:
        verify_workspace_owner(workspace_id, email)

    create_thread(req.thread_id, user_id=email, workspace_id=workspace_id)
    verify_thread_owner(req.thread_id, email)

    if workspace_id:
        update_thread_workspace(req.thread_id, workspace_id)
    else:
        workspace_id = get_thread_workspace_id(req.thread_id)

    save_message(req.thread_id, "user", req.message)
    increment_chat_count(email)
    context, sources = _workspace_context(workspace_id, req.message, email)

    def generate():
        full_response = []
        status = "complete"
        closed = False
        try:
            for chunk in stream_response(
                req.thread_id,
                req.message,
                document_context=context,
                user_email=email,
            ):
                full_response.append(chunk)
                yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"
            yield json.dumps({"sources": sources}, ensure_ascii=False) + "\n"
        except GeneratorExit:
            closed = True
            status = "stopped"
            logger.info("Stream closed for thread %s", req.thread_id[:8])
        except asyncio.CancelledError:
            closed = True
            status = "stopped"
            logger.info("Stream cancelled for thread %s", req.thread_id[:8])
        except Exception as exc:
            status = "failed"
            record_event(email, "failure", "chat_failed", {"error": str(exc)})
            logger.error("Stream error: %s: %s", type(exc).__name__, exc)
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"
        finally:
            _save_assistant_stream_result(
                req.thread_id,
                req.message,
                full_response,
                sources,
                workspace_id,
                status,
            )
            if not closed:
                yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/threads/{thread_id}/regenerate")
def regenerate(thread_id: str, req: ChatRequest | None = None, current_user=Depends(get_current_user)):
    email = current_user["email"]
    verify_thread_owner(thread_id, email)
    last_user = get_last_user_message(thread_id)
    if not last_user:
        raise HTTPException(400, "No user message to regenerate")

    delete_messages_after(thread_id, last_user["id"])
    workspace_id = (req.workspace_id if req else None) or get_thread_workspace_id(thread_id)
    context, sources = _workspace_context(workspace_id, last_user["content"], email)

    def generate():
        full_response = []
        status = "complete"
        closed = False
        try:
            for chunk in stream_response(
                thread_id,
                last_user["content"],
                document_context=context,
                user_email=email,
            ):
                full_response.append(chunk)
                yield json.dumps({"t": chunk}, ensure_ascii=False) + "\n"
            yield json.dumps({"sources": sources}, ensure_ascii=False) + "\n"
        except GeneratorExit:
            closed = True
            status = "stopped"
        except Exception as exc:
            status = "failed"
            record_event(email, "failure", "regenerate_failed", {"error": str(exc)})
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"
        finally:
            _save_assistant_stream_result(
                thread_id,
                last_user["content"],
                full_response,
                sources,
                workspace_id,
                status,
            )
            if not closed:
                yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "AI Chatbot API is running"}
