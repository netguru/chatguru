"""Title generation provider adapters."""

from title_generation.adapters.fallback import FallbackTitleGenerator
from title_generation.adapters.openai import OpenAITitleGenerator

__all__ = ["FallbackTitleGenerator", "OpenAITitleGenerator"]
