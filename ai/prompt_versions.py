# ai/prompt_versions.py
"""
Prompt version registry for A/B testing and rollback.
"""
from __future__ import annotations

from ai.prompt_builder import build_system_prompt, PromptContext

PROMPT_VERSION = "v1.0"

# Registry allows swapping prompt builders by version string
_BUILDERS = {
    "v1.0": build_system_prompt,
}


def get_prompt_builder(version: str = PROMPT_VERSION):
    """Return the prompt builder function for a given version."""
    return _BUILDERS.get(version, build_system_prompt)
