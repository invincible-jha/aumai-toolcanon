"""Tests for CLI entry points."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from aumai_toolcanon.cli import main


class TestCLIVersion:
    def test_version_flag_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_version_flag_reports_correct_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert "0.1.0" in result.output


class TestCLIHelp:
    def test_help_flag_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_help_mentions_canonicalize(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "canonicalize" in result.output

    def test_help_mentions_emit(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "emit" in result.output

    def test_help_mentions_detect(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "detect" in result.output


class TestCLICanonicalize:
    def test_canonicalize_openai_to_stdout(self, tmp_openai_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["canonicalize", "--input", str(tmp_openai_json)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "search_web"

    def test_canonicalize_produces_valid_json(self, tmp_openai_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["canonicalize", "--input", str(tmp_openai_json)])
        assert result.exit_code == 0
        # Must be parseable JSON
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_canonicalize_includes_source_format_in_output(
        self, tmp_openai_json: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["canonicalize", "--input", str(tmp_openai_json)])
        data = json.loads(result.output)
        assert data["source_format"] == "openai"

    def test_canonicalize_with_explicit_source_format(
        self, tmp_anthropic_json: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "canonicalize",
                "--input",
                str(tmp_anthropic_json),
                "--source-format",
                "anthropic",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "read_file"

    def test_canonicalize_writes_to_output_file(
        self, tmp_openai_json: Path, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "output.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "canonicalize",
                "--input",
                str(tmp_openai_json),
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["name"] == "search_web"

    def test_canonicalize_output_file_message_printed(
        self, tmp_openai_json: Path, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "result.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "canonicalize",
                "--input",
                str(tmp_openai_json),
                "--output",
                str(output_file),
            ],
        )
        assert (
            "Canonical tool written" in result.output
            or str(output_file) in result.output
        )

    def test_canonicalize_missing_input_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["canonicalize", "--input", "/nonexistent/path.json"]
        )
        assert result.exit_code != 0

    def test_canonicalize_anthropic_format(self, tmp_anthropic_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["canonicalize", "--input", str(tmp_anthropic_json)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "read_file"
        assert data["source_format"] == "anthropic"

    def test_canonicalize_warnings_emitted_for_missing_description(
        self, tmp_path: Path
    ) -> None:
        # Create a tool with no description to trigger a warning.
        # CliRunner merges stdout/stderr by default, so we check combined output.
        tool_def: dict[str, Any] = {
            "type": "function",
            "function": {"name": "no_desc", "parameters": {}},
        }
        input_file = tmp_path / "nodesc.json"
        input_file.write_text(json.dumps(tool_def), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["canonicalize", "--input", str(input_file)])
        assert result.exit_code == 0
        # Warning should appear somewhere in combined output
        assert "Warning" in result.output or "description" in result.output

    def test_canonicalize_mcp_format(self, tmp_mcp_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["canonicalize", "--input", str(tmp_mcp_json)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "list_directory"


class TestCLIEmit:
    def test_emit_to_openai_format(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["emit", "--input", str(tmp_canonical_json), "--target", "openai"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "function"
        assert "function" in data

    def test_emit_to_anthropic_format(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["emit", "--input", str(tmp_canonical_json), "--target", "anthropic"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "input_schema" in data

    def test_emit_to_mcp_format(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["emit", "--input", str(tmp_canonical_json), "--target", "mcp"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputSchema" in data

    def test_emit_to_json_schema_format(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["emit", "--input", str(tmp_canonical_json), "--target", "json-schema"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "$schema" in data

    def test_emit_preserves_name(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["emit", "--input", str(tmp_canonical_json), "--target", "anthropic"]
        )
        data = json.loads(result.output)
        assert data["name"] == "search_web"

    def test_emit_writes_to_output_file(
        self, tmp_canonical_json: Path, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "emitted.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "emit",
                "--input",
                str(tmp_canonical_json),
                "--target",
                "openai",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_emit_invalid_target_exits_nonzero(self, tmp_canonical_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["emit", "--input", str(tmp_canonical_json), "--target", "invalid_format"],
        )
        assert result.exit_code != 0

    def test_emit_missing_input_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["emit", "--input", "/no/such/file.json", "--target", "openai"]
        )
        assert result.exit_code != 0


class TestCLIDetect:
    def test_detect_openai_format(self, tmp_openai_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["detect", "--input", str(tmp_openai_json)])
        assert result.exit_code == 0
        assert "openai" in result.output

    def test_detect_anthropic_format(self, tmp_anthropic_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["detect", "--input", str(tmp_anthropic_json)])
        assert result.exit_code == 0
        assert "anthropic" in result.output

    def test_detect_mcp_format(self, tmp_mcp_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["detect", "--input", str(tmp_mcp_json)])
        assert result.exit_code == 0
        assert "mcp" in result.output

    def test_detect_verbose_shows_confidence_scores(
        self, tmp_openai_json: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["detect", "--input", str(tmp_openai_json), "--verbose"]
        )
        assert result.exit_code == 0
        assert "Confidence" in result.output or "%" in result.output

    def test_detect_verbose_shows_all_formats(self, tmp_openai_json: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["detect", "--input", str(tmp_openai_json), "--verbose"]
        )
        assert "openai" in result.output
        assert "anthropic" in result.output
        assert "mcp" in result.output

    def test_detect_missing_input_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["detect", "--input", "/nonexistent/file.json"])
        assert result.exit_code != 0
