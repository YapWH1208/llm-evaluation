"""Prompt-template validation and deterministic substitution for run snapshots."""

from __future__ import annotations

import re
from collections.abc import Mapping


ALLOWED_TEMPLATE_VARIABLES = frozenset(
    {"question", "choices", "context", "image", "audio", "video", "language", "output_schema"}
)
_VARIABLE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptTemplateError(ValueError):
    pass


def validate_template(template: str) -> set[str]:
    """Reject unsupported interpolation variables at package-registration time."""

    variables = set(_VARIABLE.findall(template))
    unsupported = sorted(variables - ALLOWED_TEMPLATE_VARIABLES)
    if unsupported:
        raise PromptTemplateError("Unsupported template variable(s): " + ", ".join(unsupported))
    return variables


def render_template(template: str, values: Mapping[str, object]) -> str:
    """Render only the explicitly supported variables with deterministic values."""

    validate_template(template)

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name, "")
        return str(value)

    return _VARIABLE.sub(substitute, template)


def standardization_flags(prompt: object) -> list[str]:
    """Expose non-standard prompt evidence without changing the prompt itself."""

    prompt_type = str(getattr(prompt, "prompt_type", "user_custom"))
    if prompt_type == "official":
        return []
    flags = ["non_standard_prompt"]
    if getattr(prompt, "system_message", None):
        flags.append("modified_system_message")
    if getattr(prompt, "output_format", None):
        flags.append("modified_output_format")
    if getattr(prompt, "few_shot_examples", None):
        flags.append("custom_few_shot")
    return flags
