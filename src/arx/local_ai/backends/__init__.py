"""Typed backend adapters; none accept arbitrary shell command text."""

from .generic import GenericBackendAdapter
from .llama_cpp import LlamaCppBackendAdapter
from .openai_compatible import OpenAICompatibleBackendAdapter

__all__ = [
    "GenericBackendAdapter",
    "LlamaCppBackendAdapter",
    "OpenAICompatibleBackendAdapter",
]
