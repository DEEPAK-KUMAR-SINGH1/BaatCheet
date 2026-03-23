from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    thread_id: str
    message: str

class NewThreadRequest(BaseModel):
    thread_id: str
    title: Optional[str] = "New Chat"

class ThreadTitleRequest(BaseModel):
    title: str

class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str

class ThreadResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
