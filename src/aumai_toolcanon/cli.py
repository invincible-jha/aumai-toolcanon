"""CLI entry point for aumai-toolcanon."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from aumai_toolcanon.models import SourceFormat


@click.group()
@click.version_option()
def main() -> None:
    """AumAI ToolCanon — normalize tool definitions to canonical IR."""


@main.command("canonicalize")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON file containing the tool definition.",
)
@click.option(
    "--source-format",
    type=click.Choice([f.value for f in SourceFormat]),
    default=None,
    help="Source format (auto-detected if omitted).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write canonical JSON to this file (default: stdout).",
)
def canonicalize(
    input_file: Path, source_format: str | None, output: Path | None
) -> None:
    """Canonicalize a tool definition to the AumAI Tool IR."""
    from aumai_toolcanon.core import Canonicalizer

    tool_def: dict[str, object] = json.loads(input_file.read_text(encoding="utf-8"))
    fmt: SourceFormat | None = SourceFormat(source_format) if source_format else None

    canon = Canonicalizer()
    result = canon.canonicalize(tool_def, fmt)

    for warning in result.warnings:
        click.echo(f"Warning: {warning}", err=True)

    output_json = json.dumps(result.tool.model_dump(mode="json"), indent=2)
    if output:
        output.write_text(output_json, encoding="utf-8")
        click.echo(f"Canonical tool written to {output}")
    else:
        click.echo(output_json)


@main.command("emit")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON file containing a CanonicalTool.",
)
@click.option(
    "--target",
    required=True,
    type=click.Choice(["openai", "anthropic", "mcp", "json-schema"]),
    help="Target output format.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write emitted JSON to file (default: stdout).",
)
def emit(input_file: Path, target: str, output: Path | None) -> None:
    """Emit a canonical tool definition to a target format."""
    from aumai_toolcanon.emitter import (
        emit_anthropic,
        emit_json_schema,
        emit_mcp,
        emit_openai,
    )
    from aumai_toolcanon.models import CanonicalTool

    raw: dict[str, object] = json.loads(input_file.read_text(encoding="utf-8"))
    tool = CanonicalTool.model_validate(raw)

    emitter_map = {
        "openai": emit_openai,
        "anthropic": emit_anthropic,
        "mcp": emit_mcp,
        "json-schema": emit_json_schema,
    }
    emitter = emitter_map[target]
    result = emitter(tool)
    output_json = json.dumps(result, indent=2)

    if output:
        output.write_text(output_json, encoding="utf-8")
        click.echo(f"Emitted {target} tool written to {output}")
    else:
        click.echo(output_json)


@main.command("detect")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON file containing the tool definition.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Show confidence scores for all formats.",
)
def detect(input_file: Path, verbose: bool) -> None:
    """Detect the source format of a tool definition file."""
    from aumai_toolcanon.core import FormatDetector

    tool_def: dict[str, object] = json.loads(input_file.read_text(encoding="utf-8"))
    detector = FormatDetector()
    detected = detector.detect(tool_def)

    click.echo(f"Detected format: {detected.value}")

    if verbose:
        scores = detector.confidence(tool_def)
        click.echo("\nConfidence scores:")
        for fmt, score in sorted(scores.items(), key=lambda x: -x[1]):
            click.echo(f"  {fmt.value:12s}: {score:.0%}")

    sys.exit(0)


if __name__ == "__main__":
    main()
