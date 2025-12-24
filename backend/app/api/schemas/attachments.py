from __future__ import annotations

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    id: str
    owner_type: str
    owner_id: str | None
    filename: str
    content_type: str
    size_bytes: int
    url: str
    uploaded_at: str


