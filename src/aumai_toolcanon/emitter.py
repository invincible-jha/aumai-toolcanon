"""Emit canonical IR to target formats."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import CanonicalTool


def emit_openai(tool: CanonicalTool) -> dict[str, Any]:
    """Emit a CanonicalTool as an OpenAI tool definition.

    Output:
    ``{"type": "function", "function": {"name": ..., "description": ...,
    "parameters": {...}}}``
    """
    parameters = tool.inputs or {"type": "object", "properties": {}}
    if "type" not in parameters:
        parameters = {"type": "object", **parameters}

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters,
        },
    }


def emit_anthropic(tool: CanonicalTool) -> dict[str, Any]:
    """Emit a CanonicalTool as an Anthropic tool definition.

    Output:
    ``{"name": ..., "description": ..., "input_schema": {...}}``
    """
    input_schema = tool.inputs or {"type": "object", "properties": {}}
    if "type" not in input_schema:
        input_schema = {"type": "object", **input_schema}

    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": input_schema,
    }


def emit_mcp(tool: CanonicalTool) -> dict[str, Any]:
    """Emit a CanonicalTool as an MCP tool definition.

    Output:
    ``{"name": ..., "description": ..., "inputSchema": {...}}``
    """
    input_schema = tool.inputs or {"type": "object", "properties": {}}
    if "type" not in input_schema:
        input_schema = {"type": "object", **input_schema}

    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": input_schema,
    }


def emit_json_schema(tool: CanonicalTool) -> dict[str, Any]:
    """Emit a CanonicalTool as a standalone JSON Schema document.

    The resulting schema describes the tool's *input* interface in standard
    JSON Schema Draft 7 / 2019-09 format, with metadata in ``$defs``.
    """
    inputs = tool.inputs or {"type": "object", "properties": {}}
    base: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "title": tool.name,
        "description": tool.description,
    }
    base.update(inputs)

    # Inject outputs as an extension annotation if available
    if tool.outputs:
        base["x-outputs"] = tool.outputs

    # Inject capability metadata as extensions
    base["x-capabilities"] = {
        "action": tool.capabilities.action,
        "domain": tool.capabilities.domain,
        "side_effects": tool.capabilities.side_effects,
        "idempotent": tool.capabilities.idempotent,
        "cost_estimate": tool.capabilities.cost_estimate,
    }

    if tool.security:
        base["x-security"] = {
            "required_permissions": tool.security.required_permissions,
            "data_classification": tool.security.data_classification,
            "pii_handling": tool.security.pii_handling,
        }

    return base


__all__ = [
    "emit_openai",
    "emit_anthropic",
    "emit_mcp",
    "emit_json_schema",
]
