"""Core canonicalization logic: format detection and normalization."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.models import (
    CanonicalTool,
    CanonicalizationResult,
    SourceFormat,
    ToolCapability,
)
from aumai_toolcanon.parsers.anthropic import AnthropicParser
from aumai_toolcanon.parsers.langchain import LangChainParser
from aumai_toolcanon.parsers.mcp import MCPParser
from aumai_toolcanon.parsers.openai import OpenAIParser


class FormatDetector:
    """Auto-detect the source format of a tool definition dict."""

    _parsers: list[tuple[SourceFormat, Any]] = []

    def __init__(self) -> None:
        self._parsers = [
            (SourceFormat.openai, OpenAIParser()),
            (SourceFormat.anthropic, AnthropicParser()),
            (SourceFormat.mcp, MCPParser()),
            (SourceFormat.langchain, LangChainParser()),
        ]

    def detect(self, tool_def: dict[str, Any]) -> SourceFormat:
        """Return the most likely SourceFormat for the given dict.

        Detection priority:
        1. OpenAI  — ``type=="function"`` wrapper or ``parameters`` key
        2. Anthropic — ``input_schema`` key
        3. MCP — ``inputSchema`` key
        4. LangChain — ``args_schema`` / ``schema`` key
        5. Raw — fallback
        """
        for fmt, parser in self._parsers:
            if parser.can_parse(tool_def):
                return fmt
        return SourceFormat.raw

    def confidence(self, tool_def: dict[str, Any]) -> dict[SourceFormat, float]:
        """Return a confidence score (0–1) for each known format."""
        scores: dict[SourceFormat, float] = {}

        # OpenAI signals
        openai_score = 0.0
        if tool_def.get("type") == "function" and "function" in tool_def:
            openai_score = 1.0
        elif "parameters" in tool_def and "name" in tool_def:
            openai_score = 0.7
        scores[SourceFormat.openai] = openai_score

        # Anthropic signals
        anthropic_score = 0.0
        if "input_schema" in tool_def and "name" in tool_def:
            anthropic_score = 1.0
        scores[SourceFormat.anthropic] = anthropic_score

        # MCP signals
        mcp_score = 0.0
        if "inputSchema" in tool_def and "name" in tool_def:
            mcp_score = 1.0
        scores[SourceFormat.mcp] = mcp_score

        # LangChain signals
        lc_score = 0.0
        if "args_schema" in tool_def or "schema" in tool_def:
            lc_score = 0.9
        elif "properties" in tool_def and "name" in tool_def:
            lc_score = 0.6
        scores[SourceFormat.langchain] = lc_score

        scores[SourceFormat.raw] = 0.1
        return scores


class Canonicalizer:
    """Normalize tool definitions from any supported format to CanonicalTool."""

    def __init__(self) -> None:
        self._detector = FormatDetector()
        self._parsers: dict[SourceFormat, Any] = {
            SourceFormat.openai: OpenAIParser(),
            SourceFormat.anthropic: AnthropicParser(),
            SourceFormat.mcp: MCPParser(),
            SourceFormat.langchain: LangChainParser(),
        }

    def canonicalize(
        self,
        tool_def: dict[str, Any],
        source_format: SourceFormat | None = None,
    ) -> CanonicalizationResult:
        """Canonicalize a tool definition dict.

        If ``source_format`` is None, auto-detection is used.
        Returns a CanonicalizationResult with the canonical tool and any warnings.
        """
        warnings: list[str] = []

        if source_format is None:
            detected = self._detector.detect(tool_def)
            if detected == SourceFormat.raw:
                warnings.append(
                    "Could not detect source format; using raw passthrough."
                )
        else:
            detected = source_format

        parser = self._parsers.get(detected)
        if parser is None:
            # Raw format — best-effort passthrough
            tool = self._raw_canonicalize(tool_def)
            warnings.append(
                "No parser for 'raw' format; extracted fields by heuristic."
            )
        else:
            try:
                tool = parser.parse(tool_def)
            except Exception as exc:
                warnings.append(f"Parser error for {detected.value}: {exc}")
                tool = self._raw_canonicalize(tool_def)

        if not tool.name:
            warnings.append("Tool has no name — consider adding one.")
        if not tool.description:
            warnings.append("Tool has no description — consider adding one.")

        return CanonicalizationResult(
            tool=tool,
            warnings=warnings,
            source_format_detected=detected,
        )

    def _raw_canonicalize(self, tool_def: dict[str, Any]) -> CanonicalTool:
        """Best-effort extraction from an unknown format."""
        name: str = (
            tool_def.get("name")
            or tool_def.get("title")
            or tool_def.get("function", {}).get("name", "")
        )
        description: str = tool_def.get("description", "")

        # Try to find parameters-like key
        inputs: dict[str, Any] = (
            tool_def.get("parameters")
            or tool_def.get("input_schema")
            or tool_def.get("inputSchema")
            or tool_def.get("schema")
            or {}
        )

        return CanonicalTool(
            name=str(name),
            description=str(description),
            capabilities=ToolCapability(),
            inputs=inputs,
            outputs={},
            source_format=SourceFormat.raw,
            original_definition=tool_def,
        )


__all__ = [
    "FormatDetector",
    "Canonicalizer",
]
