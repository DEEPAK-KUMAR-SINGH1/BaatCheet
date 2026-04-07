import os
import uuid
import shutil
import logging
from typing import Generator
from datetime import datetime

from config import load_env
load_env()

from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ─────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────

BASE_DIR       = os.path.dirname(__file__)
CHROMA_BASE    = os.path.join(BASE_DIR, "chroma_store")
UPLOADS_DIR    = os.path.join(BASE_DIR, "uploads")

os.makedirs(CHROMA_BASE, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ─────────────────────────────────────────
# LLM + EMBEDDINGS
# ─────────────────────────────────────────

llm = ChatMistralAI(model_name="mistral-large-2512", streaming=True)
embeddings = MistralAIEmbeddings(model="mistral-embed")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ".", "!", "?", ",", " "]
)

# ─────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()


# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from image using Gemini 2.0 Flash via direct HTTP.
    No SDK used — zero dependency conflicts.
    """
    try:
        import base64
        import json
        import urllib.request
        import urllib.error

        from config import GEMINI_API_KEY
        gemini_api_key = GEMINI_API_KEY
        logger.info(f"Gemini key loaded: {gemini_api_key[:8] if gemini_api_key else 'NONE'}...")
        if not gemini_api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return ""

        # Image ko base64 mein encode karo
        with open(file_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode("utf-8")

        # File extension se MIME type detect karo
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        payload = json.dumps({
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Extract all the text from this image. Return only the extracted text, nothing else."
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ]
        }).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"

        req = urllib.request.Request(
            url=url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            error_body = http_err.read().decode("utf-8")
            logger.error(f"Gemini HTTP {http_err.code}: {error_body}")
            return ""

        extracted = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        if extracted:
            logger.info(f"Gemini extracted {len(extracted)} chars from image")
        else:
            logger.warning("Gemini returned empty text for image")
        return extracted

    except Exception as e:
        logger.error(f"Gemini image extraction failed: {e}")
        return ""


def extract_text(file_path: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return extract_text_from_image(file_path)
    elif ext in [".txt", ".md", ".csv"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ─────────────────────────────────────────
# CHROMA VECTOR STORE — per thread
# ─────────────────────────────────────────

def get_vectorstore(thread_id: str) -> Chroma:
    persist_dir = os.path.join(CHROMA_BASE, thread_id)
    return Chroma(
        collection_name=f"thread_{thread_id}",
        embedding_function=embeddings,
        persist_directory=persist_dir
    )


def add_document_to_store(thread_id: str, text: str, doc_name: str, doc_id: str):
    """Chunked text ko Chroma mein store karo."""
    chunks = splitter.split_text(text)
    docs = [
        Document(
            page_content=chunk,
            metadata={
                "doc_id":   doc_id,
                "doc_name": doc_name,
                "chunk":    i,
                "thread_id": thread_id
            }
        )
        for i, chunk in enumerate(chunks)
    ]
    vs = get_vectorstore(thread_id)
    vs.add_documents(docs)
    return len(chunks)


def retrieve_context(thread_id: str, query: str, k: int = 5) -> str:
    """Query ke basis pe relevant chunks retrieve karo."""
    vs = get_vectorstore(thread_id)
    # Collection empty check
    try:
        results = vs.similarity_search(query, k=k)
    except Exception:
        return ""
    if not results:
        return ""
    parts = []
    for doc in results:
        name = doc.metadata.get("doc_name", "document")
        parts.append(f"[From: {name}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def delete_thread_store(thread_id: str):
    """Thread delete hone pe uska Chroma store bhi delete karo."""
    persist_dir = os.path.join(CHROMA_BASE, thread_id)
    if os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)


def delete_doc_from_store(thread_id: str, doc_id: str):
    """Specific document ke chunks delete karo."""
    vs = get_vectorstore(thread_id)
    vs.delete(where={"doc_id": doc_id})


# ─────────────────────────────────────────
# RAG STREAMING RESPONSE
# ─────────────────────────────────────────

RAG_SYSTEM = """You are a highly intelligent AI assistant. Today's date is {date}.

You have access to documents uploaded by the user. Use them to answer questions accurately.

## Rules:
- Answer ONLY from the provided document context when the question is about the documents.
- If the answer is not in the documents, say so clearly — do not hallucinate.
- For general questions (not about documents), answer from your own knowledge.
- Respond in the SAME language the user writes in.
- Use proper Markdown formatting: headings, bold, bullet points, code blocks.
- Be concise but complete.
- Always cite which document the information came from when using document context.
"""

def stream_rag_response(
    thread_id: str,
    user_message: str,
    chat_history: list,
) -> Generator[str, None, None]:
    """
    RAG pipeline with conversation history streaming.
    chat_history: list of {"role": "user"/"assistant", "content": "..."}
    """

    # 1. Relevant context retrieve karo
    context = retrieve_context(thread_id, user_message, k=5)

    # 2. System prompt build karo
    system_content = RAG_SYSTEM.format(date=datetime.now().strftime("%d %B %Y, %A"))

    if context:
        system_content += f"\n\n## Relevant Document Content:\n\n{context}"

    messages = [SystemMessage(content=system_content)]

    # 3. Chat history add karo (last 10 turns)
    for msg in chat_history[-10:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # 4. Current user message
    messages.append(HumanMessage(content=user_message))

    # 5. Stream response
    for chunk in llm.stream(messages):
        if chunk.content:
            yield chunk.content