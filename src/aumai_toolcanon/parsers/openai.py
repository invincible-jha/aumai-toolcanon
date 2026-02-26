"""Parser for OpenAI function calling / tool format."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import CanonicalTool, SourceFormat, ToolCapability


class OpenAIParser:
    """Parse OpenAI function calling tool definitions into CanonicalTool."""

    def parse(self, tool_def: dict[str, Any]) -> CanonicalTool:
        """Parse OpenAI tool definition.

        Handles:
        - Wrapped: ``{"type": "function", "function": {...}}``
        - Legacy function call: ``{"name": ..., "parameters": {...}}``
        """
        # Unwrap tool wrapper
        if tool_def.get("type") == "function" and "function" in tool_def:
            func: dict[str, Any] = tool_def["function"]
        else:
            func = tool_def

        name: str = func.get("name", "")
        description: str = func.get("description", "")
        parameters: dict[str, Any] = func.get("parameters", {})

        # Infer capabilities from name / description
        capabilities = _infer_capabilities(name, description)

        return CanonicalTool(
            name=name,
            description=description,
            capabilities=capabilities,
            inputs=parameters,
            outputs={},
            source_format=SourceFormat.openai,
            original_definition=tool_def,
        )

    def can_parse(self, tool_def: dict[str, Any]) -> bool:
        """Return True if this dict looks like an OpenAI tool definition."""
        if tool_def.get("type") == "function" and "function" in tool_def:
            return True
        if "name" in tool_def and "parameters" in tool_def:
            return True
        return False


def _infer_capabilities(name: str, description: str) -> ToolCapability:
    """Heuristically infer tool capabilities from name and description text."""
    text = (name + " " + description).lower()

    side_effect_verbs = {"write", "create", "delete", "update", "post", "send", "save", "remove"}
    read_verbs = {"read", "get", "fetch", "list", "search", "query", "find"}

    has_side_effects = any(v in text for v in side_effect_verbs)
    action = "write" if has_side_effects else "read"
    for verb in read_verbs:
        if verb in text:
            action = verb
            break

    domain_map = {
        "file": "filesystem",
        "web": "web",
        "search": "web",
        "database": "database",
        "sql": "database",
        "code": "code",
        "email": "email",
        "http": "web",
        "api": "web",
    }
    domain = "general"
    for keyword, dom in domain_map.items():
        if keyword in text:
            domain = dom
            break

    return ToolCapability(
        action=action,
        domain=domain,
        side_effects=has_side_effects,
        idempotent=not has_side_effects,
        cost_estimate="unknown",
    )


__all__ = ["OpenAIParser"]
