"""Process-wide document RAG repository lifecycle."""

from config import get_document_rag_settings, get_logger
from document_rag.factory import build_document_rag_repository
from document_rag.repository import DocumentRagRepository

logger = get_logger(__name__)

_document_rag_repository: DocumentRagRepository | None = None


def is_document_rag_enabled() -> bool:
    """Return True when document RAG is explicitly enabled."""
    return bool(get_document_rag_settings().enabled)


async def init_document_rag() -> None:
    """Initialize process-wide document RAG repository."""
    global _document_rag_repository  # noqa: PLW0603
    if not is_document_rag_enabled():
        logger.info("Document RAG is disabled (DOCUMENT_RAG_ENABLED=false)")
        return
    if _document_rag_repository is not None:
        return
    _document_rag_repository = await build_document_rag_repository()
    logger.info("Document RAG initialized")


async def shutdown_document_rag() -> None:
    """Shutdown process-wide document RAG repository."""
    global _document_rag_repository  # noqa: PLW0603
    if _document_rag_repository is not None:
        await _document_rag_repository.close()
        _document_rag_repository = None
        logger.info("Document RAG shut down")


def get_document_rag_repository() -> DocumentRagRepository | None:
    """Get document RAG repository if enabled, otherwise None."""
    if not is_document_rag_enabled():
        return None
    if _document_rag_repository is None:
        msg = "Document RAG repository is not initialized"
        raise RuntimeError(msg)
    return _document_rag_repository
