import glob
import os
import uuid

from fastapi import HTTPException, UploadFile

from database import (
    get_document,
    record_event,
    replace_document_chunks,
    save_document_record,
    update_document_status,
)
from rag_engine import (
    UPLOADS_DIR,
    add_document_to_store,
    delete_doc_from_store,
    extract_document_pages,
)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".txt",
    ".md",
    ".csv",
    ".doc",
    ".docx",
    ".xlsx",
    ".pptx",
}
MAX_FILE_SIZE_MB = 20


def _preview_from_pages(pages: list[dict]) -> str:
    text = "\n\n".join(page.get("text", "") for page in pages).strip()
    return text[:1200]


def _saved_path(doc_id: str, ext: str) -> str:
    return os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")


def find_saved_document_path(doc_id: str):
    matches = glob.glob(os.path.join(UPLOADS_DIR, f"{doc_id}.*"))
    return matches[0] if matches else None


async def upload_and_index_document(
    *,
    thread_id: str,
    workspace_id: str,
    file: UploadFile,
    user_id: str,
    raise_on_failure: bool = False,
):
    filename = file.filename or "uploaded"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        record_event(user_id, "failure", "unsupported_file_type", {"extension": ext})
        raise HTTPException(
            400,
            f"File type '{ext}' not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        record_event(user_id, "failure", "file_too_large", {"filename": file.filename})
        raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE_MB}MB")

    doc_id = str(uuid.uuid4())
    save_path = _saved_path(doc_id, ext)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    with open(save_path, "wb") as handle:
        handle.write(content)

    save_document_record(
        doc_id=doc_id,
        thread_id=thread_id,
        workspace_id=workspace_id,
        filename=filename,
        file_type=ext,
        status="processing",
    )

    try:
        doc = index_existing_document(doc_id, workspace_id=workspace_id, user_id=user_id)
        record_event(user_id, "document_uploaded", None, {"doc_id": doc_id, "file_type": ext})
        return doc
    except HTTPException:
        record_event(user_id, "failure", "indexing_failed", {"doc_id": doc_id, "file_type": ext})
        if raise_on_failure:
            raise
        return get_document(doc_id)
    except Exception as exc:
        update_document_status(doc_id, "failed", error=str(exc))
        record_event(user_id, "failure", "indexing_failed", {"doc_id": doc_id, "error": str(exc)})
        if raise_on_failure:
            raise HTTPException(500, f"Failed to process file: {str(exc)}") from exc
        return get_document(doc_id)


def index_existing_document(doc_id: str, *, workspace_id: str, user_id: str | None = None):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.get("workspace_id") and doc["workspace_id"] != workspace_id:
        raise HTTPException(400, "Document does not belong to this workspace")

    path = find_saved_document_path(doc_id)
    if not path:
        update_document_status(doc_id, "failed", error="Original uploaded file is missing")
        record_event(user_id, "failure", "missing_upload", {"doc_id": doc_id})
        raise HTTPException(404, "Original uploaded file is missing")

    try:
        pages = extract_document_pages(path, doc["filename"])
        if not pages:
            update_document_status(doc_id, "failed", error="Could not extract text from this file.")
            record_event(user_id, "failure", "empty_extraction", {"doc_id": doc_id})
            raise HTTPException(400, "Could not extract text from this file.")

        delete_doc_from_store(workspace_id, doc_id)
        chunk_count, chunks = add_document_to_store(
            workspace_id,
            pages,
            doc["filename"],
            doc_id,
            return_chunks=True,
        )
        if chunk_count <= 0:
            update_document_status(doc_id, "failed", error="Could not create searchable chunks from this file.")
            record_event(user_id, "failure", "empty_chunks", {"doc_id": doc_id})
            raise HTTPException(400, "Could not create searchable chunks from this file.")

        replace_document_chunks(doc_id, chunks)
        return update_document_status(
            doc_id,
            "indexed",
            chunk_count=chunk_count,
            error=None,
            extracted_preview=_preview_from_pages(pages),
        )
    except HTTPException:
        raise
    except Exception as exc:
        update_document_status(doc_id, "failed", error=str(exc))
        record_event(user_id, "failure", "indexing_failed", {"doc_id": doc_id, "error": str(exc)})
        raise
