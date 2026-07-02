"""Document-to-markdown conversion using Docling."""

import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Any

from config import get_docling_settings, get_llm_settings, get_logger

logger = get_logger(__name__)

# Module-level singleton — Docling's DocumentConverter is expensive to initialise
# (loads ML models). We create it lazily on first use and reuse it thereafter.
_converter = None
_converter_lock = threading.Lock()


def _build_vision_url() -> str:
    """Derive the chat-completions URL for picture description.

    Priority:
    1. Explicit DOCLING_PICTURE_DESCRIPTION_URL override.
    2. LLM_API_BASE + LLM_API_VERSION set → Azure-style deployment path:
           <base>/openai/deployments/<model>/chat/completions?api-version=…
    3. LLM_API_BASE only → OpenAI-compatible base URL:
           <base>/chat/completions
    """
    docling = get_docling_settings()
    if docling.picture_description_url:
        return str(docling.picture_description_url)

    llm = get_llm_settings()

    if llm.api_base:
        base = llm.api_base.rstrip("/")
        # An api-version implies an Azure-style endpoint: the model/deployment
        # goes in the path and the version in the query string.
        if llm.api_version and llm.model:
            return (
                f"{base}/openai/deployments/{llm.model}"
                f"/chat/completions?api-version={llm.api_version}"
            )
        # Otherwise the base URL is already an OpenAI-compatible /v1 endpoint.
        return f"{base}/chat/completions"

    msg = (
        "Cannot derive picture description URL from LLM settings. "
        "Set DOCLING_PICTURE_DESCRIPTION_URL explicitly."
    )
    raise ValueError(msg)


def _get_converter() -> Any:
    global _converter  # noqa: PLW0603
    if _converter is not None:
        return _converter
    with _converter_lock:
        if _converter is not None:
            return _converter
        from docling.datamodel.base_models import InputFormat  # noqa: PLC0415
        from docling.datamodel.pipeline_options import (  # noqa: PLC0415
            PdfPipelineOptions,
            PictureDescriptionApiOptions,
        )
        from docling.document_converter import (  # noqa: PLC0415
            DocumentConverter,
            PdfFormatOption,
        )

        docling = get_docling_settings()

        pdf_opts = PdfPipelineOptions(do_table_structure=True)

        if docling.picture_description_enabled:
            vision_url = _build_vision_url()
            llm = get_llm_settings()
            api_key = docling.picture_description_api_key or llm.api_key
            pdf_opts.do_picture_description = True
            pdf_opts.enable_remote_services = True
            # params is spread directly into the JSON request body by Docling,
            # so passing model here is the correct way to set it for
            # OpenAI-compatible endpoints that require it.
            pdf_opts.picture_description_options = PictureDescriptionApiOptions(
                url=vision_url,  # type: ignore[arg-type]
                # Send both auth header styles: APIM / Azure proxies use "api-key";
                # standard OpenAI uses "Authorization: Bearer". Sending both is harmless.
                headers={
                    "api-key": api_key,
                    "Authorization": f"Bearer {api_key}",
                },
                params={"model": llm.model},
                prompt="Describe this image concisely, focusing on any data, charts, diagrams, or key visual elements.",
            )
            logger.info(
                "Docling picture description enabled (url=%s, model=%s)",
                vision_url,
                llm.model,
            )

        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)}
        )
    return _converter


async def prewarm_converter() -> None:
    """Load and cache the Docling converter in a thread pool (non-blocking)."""
    await asyncio.to_thread(_get_converter)


def _convert_sync(file_bytes: bytes, filename: str) -> str:
    """Run Docling conversion in the calling thread (CPU-bound)."""
    converter = _get_converter()

    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        result = converter.convert(tmp.name)

    return result.document.export_to_markdown()  # type: ignore[no-any-return]


async def convert_document_to_markdown(file_bytes: bytes, filename: str) -> str:
    """Convert a document to markdown using Docling.

    Runs the CPU-intensive conversion in a thread pool to keep the event loop
    unblocked.

    Raises:
        ValueError: If the document cannot be converted.
    """
    try:
        return await asyncio.to_thread(_convert_sync, file_bytes, filename)
    except Exception as exc:
        logger.exception("Docling conversion failed for %s", filename)
        msg = f"Failed to convert document: {filename}"
        raise ValueError(msg) from exc
