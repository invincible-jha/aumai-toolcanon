"""Quickstart examples for aumai-toolcanon.

Demonstrates the main features of the library:
  1. Auto-detecting tool definition formats
  2. Canonicalizing tools from different provider formats
  3. Emitting canonical tools to provider-specific formats
  4. Attaching security and capability metadata manually
  5. Using confidence scores for ambiguous inputs

Run this file directly to verify your installation:

    python examples/quickstart.py

All demos run without network access or API keys.
"""

from __future__ import annotations

import json

from aumai_toolcanon.core import Canonicalizer, FormatDetector
from aumai_toolcanon.emitter import (
    emit_anthropic,
    emit_json_schema,
    emit_mcp,
    emit_openai,
)
from aumai_toolcanon.models import (
    CanonicalTool,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)


# ---------------------------------------------------------------------------
# Sample tool definitions in each supported format
# ---------------------------------------------------------------------------

OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web and return the top results",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

ANTHROPIC_TOOL = {
    "name": "read_file",
    "description": "Read the contents of a file at the given path",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute file path to read",
            }
        },
        "required": ["path"],
    },
}

MCP_TOOL = {
    "name": "list_directory",
    "description": "List all files and subdirectories in a directory",
    "inputSchema": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Absolute path to the directory",
            },
            "include_hidden": {
                "type": "boolean",
                "description": "Whether to include hidden files (dotfiles)",
                "default": False,
            },
        },
        "required": ["directory"],
    },
}

LANGCHAIN_TOOL = {
    "name": "execute_sql",
    "description": "Execute a read-only SQL query against the database",
    "args_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A valid SELECT statement",
            }
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Demo 1: Auto-detection
# ---------------------------------------------------------------------------

def demo_format_detection() -> None:
    """Show how FormatDetector identifies tool definition formats."""
    print("=" * 60)
    print("DEMO 1: Format Detection")
    print("=" * 60)

    detector = FormatDetector()

    tools = {
        "OpenAI wrapped": OPENAI_TOOL,
        "Anthropic": ANTHROPIC_TOOL,
        "MCP": MCP_TOOL,
        "LangChain": LANGCHAIN_TOOL,
    }

    for label, tool_def in tools.items():
        detected = detector.detect(tool_def)
        print(f"  {label:20s} -> {detected.value}")

    print()

    # Show confidence scores for an ambiguous-looking tool
    ambiguous = {"name": "my_tool", "parameters": {"type": "object"}, "properties": {}}
    scores = detector.confidence(ambiguous)
    print("Confidence scores for an ambiguous tool definition:")
    for fmt, score in sorted(scores.items(), key=lambda x: -x[1]):
        bar = "#" * int(score * 20)
        print(f"  {fmt.value:12s}: {score:.0%}  [{bar}]")
    print()


# ---------------------------------------------------------------------------
# Demo 2: Canonicalization from different formats
# ---------------------------------------------------------------------------

def demo_canonicalization() -> None:
    """Canonicalize tools from OpenAI, Anthropic, MCP, and LangChain formats."""
    print("=" * 60)
    print("DEMO 2: Canonicalization from Multiple Formats")
    print("=" * 60)

    canon = Canonicalizer()

    tools_to_normalize = [
        ("OpenAI", OPENAI_TOOL),
        ("Anthropic", ANTHROPIC_TOOL),
        ("MCP", MCP_TOOL),
        ("LangChain", LANGCHAIN_TOOL),
    ]

    for label, raw_def in tools_to_normalize:
        result = canon.canonicalize(raw_def)
        tool = result.tool

        print(f"  [{label}] {tool.name}")
        print(f"    Detected format : {result.source_format_detected.value}")
        print(f"    Action          : {tool.capabilities.action}")
        print(f"    Domain          : {tool.capabilities.domain}")
        print(f"    Side effects    : {tool.capabilities.side_effects}")
        print(f"    Idempotent      : {tool.capabilities.idempotent}")
        if result.warnings:
            print(f"    Warnings        : {result.warnings}")
        print()


# ---------------------------------------------------------------------------
# Demo 3: Round-trip emit to all target formats
# ---------------------------------------------------------------------------

def demo_emit_formats() -> None:
    """Canonicalize one tool and emit it to all four target formats."""
    print("=" * 60)
    print("DEMO 3: Emitting to All Target Formats")
    print("=" * 60)

    canon = Canonicalizer()
    result = canon.canonicalize(OPENAI_TOOL)
    tool = result.tool

    print(f"Source tool: '{tool.name}' (detected as {result.source_format_detected.value})")
    print()

    # Emit to each supported format
    openai_out    = emit_openai(tool)
    anthropic_out = emit_anthropic(tool)
    mcp_out       = emit_mcp(tool)
    schema_out    = emit_json_schema(tool)

    print("OpenAI format:")
    print(json.dumps(openai_out, indent=2))
    print()

    print("Anthropic format:")
    print(json.dumps(anthropic_out, indent=2))
    print()

    print("MCP format:")
    print(json.dumps(mcp_out, indent=2))
    print()

    # JSON Schema output includes x-capabilities vendor extension
    print("JSON Schema (x-capabilities extension):")
    print(json.dumps(schema_out.get("x-capabilities", {}), indent=2))
    print()


# ---------------------------------------------------------------------------
# Demo 4: Manual construction with security metadata
# ---------------------------------------------------------------------------

def demo_security_metadata() -> None:
    """Build a CanonicalTool manually with full security metadata."""
    print("=" * 60)
    print("DEMO 4: Manual Construction with Security Metadata")
    print("=" * 60)

    # Construct the tool explicitly — useful for tools that don't come from
    # a provider format (e.g., internal tools registered directly in a registry)
    tool = CanonicalTool(
        name="delete_customer_record",
        version="2.1.0",
        description="Permanently delete a customer record and all associated data",
        capabilities=ToolCapability(
            action="delete",
            domain="database",
            side_effects=True,
            idempotent=False,
            cost_estimate="low",
        ),
        security=ToolSecurity(
            required_permissions=["db:write", "customers:delete", "audit:log"],
            data_classification="confidential",
            pii_handling="processes",
        ),
        inputs={
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "UUID of the customer to delete",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to confirm the deletion",
                },
            },
            "required": ["customer_id", "confirm"],
        },
        source_format=SourceFormat.raw,
    )

    print(f"Tool: {tool.name} (v{tool.version})")
    print(f"  Side effects : {tool.capabilities.side_effects}")
    print(f"  Idempotent   : {tool.capabilities.idempotent}")
    print(f"  Permissions  : {tool.security.required_permissions}")  # type: ignore[union-attr]
    print(f"  Classification: {tool.security.data_classification}")  # type: ignore[union-attr]
    print()

    # The JSON Schema emitter embeds security metadata as x-security
    schema = emit_json_schema(tool)
    print("JSON Schema x-security extension:")
    print(json.dumps(schema.get("x-security", {}), indent=2))
    print()


# ---------------------------------------------------------------------------
# Demo 5: Batch canonicalization with warning collection
# ---------------------------------------------------------------------------

def demo_batch_with_warnings() -> None:
    """Canonicalize a mixed batch of tool definitions and collect warnings."""
    print("=" * 60)
    print("DEMO 5: Batch Canonicalization with Warning Collection")
    print("=" * 60)

    # Mix of good and incomplete tool definitions
    raw_tools = [
        OPENAI_TOOL,
        ANTHROPIC_TOOL,
        MCP_TOOL,
        # A tool with no name or description — will generate warnings
        {"type": "function", "function": {"parameters": {"type": "object"}}},
        # A completely unknown format — will use raw fallback
        {"custom_schema": {"field": "value"}, "title": "my_custom_tool"},
    ]

    canon = Canonicalizer()
    all_warnings: list[tuple[str, list[str]]] = []

    print(f"Processing {len(raw_tools)} tool definitions...\n")

    for index, raw_def in enumerate(raw_tools):
        result = canon.canonicalize(raw_def)
        tool_name = result.tool.name or f"<unnamed tool #{index + 1}>"

        status = "OK" if not result.warnings else "WARN"
        print(f"  [{status}] {tool_name} (format: {result.source_format_detected.value})")

        if result.warnings:
            all_warnings.append((tool_name, result.warnings))

    print()
    if all_warnings:
        print("Warning summary:")
        for tool_name, warnings in all_warnings:
            for warning in warnings:
                print(f"  {tool_name}: {warning}")
    else:
        print("No warnings.")
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run all quickstart demos."""
    print()
    print("aumai-toolcanon Quickstart")
    print("Normalize tool definitions to Canonical IR")
    print()

    demo_format_detection()
    demo_canonicalization()
    demo_emit_formats()
    demo_security_metadata()
    demo_batch_with_warnings()

    print("All demos complete.")


if __name__ == "__main__":
    main()
