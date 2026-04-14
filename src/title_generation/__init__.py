"""Title generation package: port, adapters, factory, and bootstrap."""

from title_generation.bootstrap import (
    generate_title,
    get_title_generator,
    init_title_generation,
    shutdown_title_generation,
)
from title_generation.factory import build_title_generator
from title_generation.repository import TitleGenerator
from title_generation.utils import truncate_title

__all__ = [
    "TitleGenerator",
    "build_title_generator",
    "generate_title",
    "get_title_generator",
    "init_title_generation",
    "shutdown_title_generation",
    "truncate_title",
]
