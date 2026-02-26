"""Pydantic models for aumai-toolcanon."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    """Supported tool definition source formats."""

    openai = "openai"
    anthropic = "anthropic"
    mcp = "mcp"
    langchain = "langchain"
    raw = "raw"


class ToolCapability(BaseModel):
    """Semantic capability metadata for a tool."""

    action: str = Field(
        default="",
        description="Primary action verb: read, write, call, search, etc.",
    )
    domain: str = Field(
        default="",
        description="Domain: filesystem, web, database, code, etc.",
    )
    side_effects: bool = Field(
        default=False,
        description="Whether the tool has side effects (writes, deletes, etc.)",
    )
    idempotent: bool = Field(
        default=True,
        description="Whether repeated calls produce the same result.",
    )
    cost_estimate: str = Field(
        default="unknown",
        description="Cost estimate: free, low, medium, high.",
    )


class ToolSecurity(BaseModel):
    """Security and data handling metadata for a tool."""

    required_permissions: list[str] = Field(default_factory=list)
    data_classification: str = Field(
        default="public",
        description="Data classification: public, internal, confidential, restricted.",
    )
    pii_handling: str = Field(
        default="none",
        description="PII handling: none, processes, stores, anonymizes.",
    )


class CanonicalTool(BaseModel):
    """AumAI Tool Canonical Intermediate Representation (IR)."""

    name: str = Field(..., description="Normalized tool name")
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    capabilities: ToolCapability = Field(default_factory=ToolCapability)
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema object for inputs",
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema object for outputs",
    )
    security: ToolSecurity | None = None
    source_format: SourceFormat = Field(default=SourceFormat.raw)
    original_definition: dict[str, Any] = Field(default_factory=dict)


class CanonicalizationResult(BaseModel):
    """Result of canonicalizing a tool definition."""

    tool: CanonicalTool
    warnings: list[str] = Field(default_factory=list)
    source_format_detected: SourceFormat


__all__ = [
    "SourceFormat",
    "ToolCapability",
    "ToolSecurity",
    "CanonicalTool",
    "CanonicalizationResult",
]
