"""Tests for core.py: FormatDetector and Canonicalizer."""

from __future__ import annotations

from typing import Any

from aumai_toolcanon.core import Canonicalizer, FormatDetector
from aumai_toolcanon.models import CanonicalTool, SourceFormat

# ---------------------------------------------------------------------------
# FormatDetector.detect
# ---------------------------------------------------------------------------


class TestFormatDetectorDetect:
    def test_detects_openai_wrapped(self, openai_wrapped_tool: dict[str, Any]) -> None:
        detector = FormatDetector()
        assert detector.detect(openai_wrapped_tool) is SourceFormat.openai

    def test_detects_openai_legacy(self, openai_legacy_tool: dict[str, Any]) -> None:
        detector = FormatDetector()
        assert detector.detect(openai_legacy_tool) is SourceFormat.openai

    def test_detects_anthropic(self, anthropic_tool: dict[str, Any]) -> None:
        detector = FormatDetector()
        # OpenAI parser checks first but will not match anthropic (no "parameters" key)
        # Anthropic has "input_schema", OpenAI parser checks for "parameters"
        detected = detector.detect(anthropic_tool)
        assert detected is SourceFormat.anthropic

    def test_detects_mcp(self, mcp_tool: dict[str, Any]) -> None:
        detector = FormatDetector()
        detected = detector.detect(mcp_tool)
        assert detected is SourceFormat.mcp

    def test_detects_langchain_args_schema(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        assert detector.detect(langchain_args_schema_tool) is SourceFormat.langchain

    def test_detects_langchain_schema_key(
        self, langchain_schema_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        assert detector.detect(langchain_schema_tool) is SourceFormat.langchain

    def test_unknown_format_falls_back_to_raw(self) -> None:
        detector = FormatDetector()
        assert detector.detect({"totally_unknown": True}) is SourceFormat.raw

    def test_empty_dict_falls_back_to_raw(self) -> None:
        detector = FormatDetector()
        assert detector.detect({}) is SourceFormat.raw


# ---------------------------------------------------------------------------
# FormatDetector.confidence
# ---------------------------------------------------------------------------


class TestFormatDetectorConfidence:
    def test_openai_wrapped_scores_high_for_openai(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        scores = detector.confidence(openai_wrapped_tool)
        assert scores[SourceFormat.openai] == 1.0

    def test_anthropic_tool_scores_high_for_anthropic(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        scores = detector.confidence(anthropic_tool)
        assert scores[SourceFormat.anthropic] == 1.0

    def test_mcp_tool_scores_high_for_mcp(self, mcp_tool: dict[str, Any]) -> None:
        detector = FormatDetector()
        scores = detector.confidence(mcp_tool)
        assert scores[SourceFormat.mcp] == 1.0

    def test_all_formats_present_in_scores(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        scores = detector.confidence(openai_wrapped_tool)
        for fmt in SourceFormat:
            assert fmt in scores

    def test_raw_always_has_nonzero_score(self) -> None:
        detector = FormatDetector()
        scores = detector.confidence({})
        assert scores[SourceFormat.raw] > 0

    def test_legacy_openai_scores_partial(self) -> None:
        detector = FormatDetector()
        tool_def = {"name": "t", "parameters": {}}
        scores = detector.confidence(tool_def)
        assert scores[SourceFormat.openai] == 0.7

    def test_langchain_args_schema_scores_high(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        detector = FormatDetector()
        scores = detector.confidence(langchain_args_schema_tool)
        assert scores[SourceFormat.langchain] >= 0.9

    def test_langchain_direct_properties_scores_partial(self) -> None:
        detector = FormatDetector()
        tool_def = {"name": "t", "description": "d", "properties": {}}
        scores = detector.confidence(tool_def)
        assert scores[SourceFormat.langchain] == 0.6

    def test_empty_dict_gives_zero_for_specific_formats(self) -> None:
        detector = FormatDetector()
        scores = detector.confidence({})
        assert scores[SourceFormat.openai] == 0.0
        assert scores[SourceFormat.anthropic] == 0.0
        assert scores[SourceFormat.mcp] == 0.0


# ---------------------------------------------------------------------------
# Canonicalizer.canonicalize — auto-detection
# ---------------------------------------------------------------------------


class TestCanonicalizerAutoDetect:
    def test_canonicalize_openai_wrapped(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        assert result.source_format_detected is SourceFormat.openai
        assert result.tool.name == "search_web"

    def test_canonicalize_openai_legacy(
        self, openai_legacy_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_legacy_tool)
        assert result.source_format_detected is SourceFormat.openai
        assert result.tool.name == "get_weather"

    def test_canonicalize_anthropic(self, anthropic_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        assert result.source_format_detected is SourceFormat.anthropic
        assert result.tool.name == "read_file"

    def test_canonicalize_mcp(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool)
        assert result.source_format_detected is SourceFormat.mcp
        assert result.tool.name == "list_directory"

    def test_canonicalize_langchain(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(langchain_args_schema_tool)
        assert result.source_format_detected is SourceFormat.langchain
        assert result.tool.name == "send_email"

    def test_canonicalize_unknown_format_gives_raw_result_with_warning(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize({"totally_unknown": "data"})
        assert result.source_format_detected is SourceFormat.raw
        assert any("raw" in w.lower() or "detect" in w.lower() for w in result.warnings)

    def test_result_is_canonicalization_result_instance(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        from aumai_toolcanon.models import CanonicalizationResult

        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        assert isinstance(result, CanonicalizationResult)

    def test_result_tool_is_canonical_tool_instance(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(anthropic_tool)
        assert isinstance(result.tool, CanonicalTool)


# ---------------------------------------------------------------------------
# Canonicalizer.canonicalize — explicit source_format
# ---------------------------------------------------------------------------


class TestCanonicalizerExplicitFormat:
    def test_explicit_openai_format(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(
            openai_wrapped_tool, source_format=SourceFormat.openai
        )
        assert result.source_format_detected is SourceFormat.openai
        assert result.tool.name == "search_web"

    def test_explicit_anthropic_format(
        self, anthropic_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(
            anthropic_tool, source_format=SourceFormat.anthropic
        )
        assert result.source_format_detected is SourceFormat.anthropic

    def test_explicit_mcp_format(self, mcp_tool: dict[str, Any]) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(mcp_tool, source_format=SourceFormat.mcp)
        assert result.source_format_detected is SourceFormat.mcp

    def test_explicit_langchain_format(
        self, langchain_args_schema_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(
            langchain_args_schema_tool, source_format=SourceFormat.langchain
        )
        assert result.source_format_detected is SourceFormat.langchain

    def test_explicit_raw_format_triggers_heuristic(self) -> None:
        canon = Canonicalizer()
        tool_def = {"name": "my_tool", "description": "Does stuff."}
        result = canon.canonicalize(tool_def, source_format=SourceFormat.raw)
        # raw format falls through to _raw_canonicalize with a warning
        assert any(
            "raw" in w.lower() or "heuristic" in w.lower() for w in result.warnings
        )
        assert result.tool.name == "my_tool"


# ---------------------------------------------------------------------------
# Canonicalizer — warning conditions
# ---------------------------------------------------------------------------


class TestCanonicalizerWarnings:
    def test_no_name_produces_warning(self) -> None:
        canon = Canonicalizer()
        tool_def = {
            "type": "function",
            "function": {"description": "A nameless tool.", "parameters": {}},
        }
        result = canon.canonicalize(tool_def)
        assert any("name" in w.lower() for w in result.warnings)

    def test_no_description_produces_warning(self) -> None:
        canon = Canonicalizer()
        tool_def = {
            "type": "function",
            "function": {"name": "no_desc_tool", "parameters": {}},
        }
        result = canon.canonicalize(tool_def)
        assert any("description" in w.lower() for w in result.warnings)

    def test_well_formed_tool_has_no_warnings(
        self, openai_wrapped_tool: dict[str, Any]
    ) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(openai_wrapped_tool)
        assert result.warnings == []

    def test_raw_format_detection_adds_warning(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize({"unknown_field": 42})
        assert len(result.warnings) >= 1


# ---------------------------------------------------------------------------
# Canonicalizer — raw heuristic extraction
# ---------------------------------------------------------------------------


class TestCanonicalizerRawHeuristic:
    def test_extracts_name_field(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize({"name": "heuristic_tool"})
        # Even though format is raw, name should be extracted
        assert result.tool.name == "heuristic_tool"

    def test_extracts_title_as_name_fallback(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize({"title": "title_as_name_tool"})
        assert result.tool.name == "title_as_name_tool"

    def test_extracts_description(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize(
            {"name": "desc_tool", "description": "Has a description."}
        )
        assert result.tool.description == "Has a description."

    def test_extracts_parameters_as_inputs(self) -> None:
        canon = Canonicalizer()
        tool_def = {
            "name": "param_tool",
            "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
        }
        result = canon.canonicalize(tool_def)
        assert "x" in result.tool.inputs.get("properties", {})

    def test_extracts_input_schema_as_inputs(self) -> None:
        canon = Canonicalizer()
        tool_def = {
            "name": "schema_tool",
            "input_schema": {
                "type": "object",
                "properties": {"y": {"type": "integer"}},
            },
        }
        # This will be detected as raw-ish but let's force raw to test _raw_canonicalize
        result = canon.canonicalize(tool_def, source_format=SourceFormat.raw)
        assert "y" in result.tool.inputs.get("properties", {})

    def test_source_format_set_to_raw(self) -> None:
        canon = Canonicalizer()
        result = canon.canonicalize({"name": "raw_tool"})
        assert result.tool.source_format is SourceFormat.raw

    def test_original_definition_stored(self) -> None:
        canon = Canonicalizer()
        tool_def = {"name": "orig_tool", "custom": True}
        result = canon.canonicalize(tool_def)
        assert result.tool.original_definition == tool_def
