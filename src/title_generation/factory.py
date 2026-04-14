"""Composition root for conversation title generation."""

import importlib
import inspect

from config import get_llm_settings, get_title_generation_settings
from title_generation.adapters import FallbackTitleGenerator, OpenAITitleGenerator
from title_generation.repository import TitleGenerator


def _resolve_custom_generator(custom_class: str) -> TitleGenerator:
    """Instantiate a custom title generator from ``module.path:ClassName``."""
    module_path, separator, class_name = custom_class.partition(":")
    if not separator or not module_path or not class_name:
        msg = (
            "TITLE_GENERATION_CUSTOM_CLASS must be in the format "
            "'module.path:ClassName'"
        )
        raise ValueError(msg)

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    instance = cls()

    for method_name in ("connect", "generate", "close"):
        method = getattr(instance, method_name, None)
        if (
            method is None
            or not callable(method)
            or not inspect.iscoroutinefunction(method)
        ):
            msg = (
                "Custom title generator class must define async methods: "
                "connect, generate, close"
            )
            raise ValueError(msg)

    return instance


async def build_title_generator() -> TitleGenerator:
    """Build the configured title generation adapter and verify readiness."""
    settings = get_title_generation_settings()

    builders = {
        "openai": lambda: OpenAITitleGenerator(get_llm_settings()),
        "fallback": FallbackTitleGenerator,
    }

    provider = settings.provider.lower().strip()
    if provider == "custom":
        if not settings.custom_class.strip():
            msg = (
                "TITLE_GENERATION_CUSTOM_CLASS must be set when "
                "TITLE_GENERATION_PROVIDER=custom"
            )
            raise ValueError(msg)
        generator = _resolve_custom_generator(settings.custom_class.strip())
    elif provider in builders:
        generator = builders[provider]()
    else:
        msg = (
            "Unsupported TITLE_GENERATION_PROVIDER. "
            "Use one of: openai, fallback, custom"
        )
        raise ValueError(msg)

    await generator.connect()
    return generator
