"""Title generation provider adapters."""

from title_generation.adapters.fallback import FallbackTitleGenerator
from title_generation.adapters.llm import LLMTitleGenerator

# Backwards-compatible alias for the former provider-named class.
OpenAITitleGenerator = LLMTitleGenerator

__all__ = ["FallbackTitleGenerator", "LLMTitleGenerator", "OpenAITitleGenerator"]
