"""REST endpoint for document-to-markdown conversion via Docling."""

from fastapi import APIRouter, HTTPException, UploadFile

from config import get_docling_settings, get_logger
from document_processing.service import convert_document_to_markdown

logger = get_logger(__name__)

router = APIRouter()


@router.post("/process-document")
async def process_document(file: UploadFile) -> dict[str, str]:
    """Accept a document upload, convert it to markdown with Docling, and return the result."""
    settings = get_docling_settings()

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Document processing is disabled")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_bytes = await file.read()

    if len(file_bytes) > settings.max_file_size_bytes:
        max_mb = settings.max_file_size_bytes // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File exceeds {max_mb}MB limit")

    try:
        markdown = await convert_document_to_markdown(file_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"markdown": markdown, "filename": file.filename}
