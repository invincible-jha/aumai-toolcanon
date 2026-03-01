"""Tests for the four foundation-library integrations.

Covers:
- async_core.py  — AsyncCanonicalizer (lifecycle, canonicalize, detect_format,
                    confidence, events, error paths)
- store.py        — StoredTool, ToolStore (CRUD, query methods, lifecycle)
- enricher.py     — EnrichmentResult, SchemaEnricher, EnrichmentError
- integration.py  — ToolCanonIntegration, register_with_aumos

All tests use in-memory backends (Store.memory(), MockProvider) so no network
calls or disk I/O are required.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import pytest_asyncio

from aumai_async_core import AsyncServiceConfig
from aumai_integration import AumOS

from aumai_toolcanon.async_core import AsyncCanonicalizer
from aumai_toolcanon.enricher import (
    EnrichmentError,
    EnrichmentResult,
    SchemaEnricher,
)
from aumai_toolcanon.integration import (
    ToolCanonIntegration,
    register_with_aumos,
)
from aumai_toolcanon.models import (
    CanonicalTool,
    CanonicalizationResult,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)
from aumai_toolcanon.store import StoredTool, ToolStore


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_config(name: str = "test-service") -> AsyncServiceConfig:
    return AsyncServiceConfig(
        name=name,
        max_concurrency=10,
        shutdown_timeout_seconds=5.0,
        health_check_interval_seconds=0,  # disable periodic background checks in tests
    )


def _openai_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    }


def _anthropic_tool() -> dict[str, Any]:
    return {
        "name": "read_file",
        "description": "Read a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    }


def _mcp_tool() -> dict[str, Any]:
    return {
        "name": "list_directory",
        "description": "List files in a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }


def _canonical_tool(
    name: str = "search_web",
    domain: str = "web",
    action: str = "search",
    side_effects: bool = False,
    has_security: bool = True,
) -> CanonicalTool:
    security = None
    if has_security:
        security = ToolSecurity(
            required_permissions=["internet"],
            data_classification="public",
            pii_handling="none",
        )
    return CanonicalTool(
        name=name,
        description=f"A tool that {action}s.",
        capabilities=ToolCapability(
            action=action,
            domain=domain,
            side_effects=side_effects,
            idempotent=not side_effects,
            cost_estimate="low",
        ),
        inputs={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        outputs={},
        security=security,
        source_format=SourceFormat.openai,
    )


def _enrichment_json(**overrides: Any) -> str:
    base: dict[str, Any] = {
        "capabilities": ["read", "filesystem"],
        "security_tags": ["filesystem_access"],
        "pii_tags": [],
        "description_enhancement": "Reads a file from disk.",
        "confidence": 0.9,
    }
    base.update(overrides)
    return json.dumps(base)


# ===========================================================================
# 1. async_core.py — AsyncCanonicalizer
# ===========================================================================


class TestAsyncCanonicalizerLifecycle:
    """Service lifecycle state machine."""

    @pytest.mark.asyncio
    async def test_starts_and_stops_cleanly(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        await svc.start()
        assert svc.status.state == "running"
        await svc.stop()
        assert svc.status.state == "stopped"

    @pytest.mark.asyncio
    async def test_context_manager_starts_and_stops(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            assert svc.status.state == "running"

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_running(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            healthy = await svc.health_check()
            assert healthy is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_started(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        healthy = await svc.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_double_start_raises_runtime_error(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        await svc.start()
        with pytest.raises(RuntimeError):
            await svc.start()
        await svc.stop()

    @pytest.mark.asyncio
    async def test_emitter_property_is_accessible(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        emitter = svc.emitter
        assert emitter is not None


class TestAsyncCanonicalizerCanonicalize:
    """canonicalize() method correctness and event emission."""

    @pytest.mark.asyncio
    async def test_canonicalize_openai_tool(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            result = await svc.canonicalize(_openai_tool())
            assert isinstance(result, CanonicalizationResult)
            assert result.tool.name == "search_web"
            assert result.source_format_detected is SourceFormat.openai

    @pytest.mark.asyncio
    async def test_canonicalize_anthropic_tool(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            result = await svc.canonicalize(_anthropic_tool())
            assert result.tool.name == "read_file"
            assert result.source_format_detected is SourceFormat.anthropic

    @pytest.mark.asyncio
    async def test_canonicalize_mcp_tool(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            result = await svc.canonicalize(_mcp_tool())
            assert result.tool.name == "list_directory"
            assert result.source_format_detected is SourceFormat.mcp

    @pytest.mark.asyncio
    async def test_explicit_format_bypasses_detection(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            result = await svc.canonicalize(
                _openai_tool(), source_format=SourceFormat.openai
            )
            assert result.source_format_detected is SourceFormat.openai

    @pytest.mark.asyncio
    async def test_emits_tool_canonicalized_event(self) -> None:
        events_received: list[dict[str, Any]] = []

        async def capture(**kwargs: Any) -> None:
            events_received.append(kwargs)

        svc = AsyncCanonicalizer(_make_config())
        svc.emitter.on("tool.canonicalized", capture)
        async with svc:
            await svc.canonicalize(_openai_tool())

        assert len(events_received) == 1
        assert events_received[0]["tool_name"] == "search_web"
        assert events_received[0]["source_format"] == "openai"

    @pytest.mark.asyncio
    async def test_request_count_increments_on_canonicalize(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            await svc.canonicalize(_openai_tool())
            await svc.canonicalize(_anthropic_tool())
            assert svc.status.request_count == 2

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_not_started(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        with pytest.raises(RuntimeError, match="not running"):
            await svc.canonicalize(_openai_tool())

    @pytest.mark.asyncio
    async def test_warnings_propagated_in_result(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            result = await svc.canonicalize({"unknown_key": True})
            # raw format — should have at least one warning
            assert len(result.warnings) >= 1


class TestAsyncCanonicalizerDetectFormat:
    """detect_format() method."""

    @pytest.mark.asyncio
    async def test_detect_openai(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            fmt = await svc.detect_format(_openai_tool())
            assert fmt is SourceFormat.openai

    @pytest.mark.asyncio
    async def test_detect_anthropic(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            fmt = await svc.detect_format(_anthropic_tool())
            assert fmt is SourceFormat.anthropic

    @pytest.mark.asyncio
    async def test_detect_mcp(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            fmt = await svc.detect_format(_mcp_tool())
            assert fmt is SourceFormat.mcp

    @pytest.mark.asyncio
    async def test_detect_unknown_returns_raw(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            fmt = await svc.detect_format({"totally_unknown": 1})
            assert fmt is SourceFormat.raw

    @pytest.mark.asyncio
    async def test_raises_when_not_started(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        with pytest.raises(RuntimeError):
            await svc.detect_format(_openai_tool())

    @pytest.mark.asyncio
    async def test_emits_format_detected_event(self) -> None:
        detected: list[str] = []

        async def capture(**kwargs: Any) -> None:
            detected.append(kwargs["source_format"])

        svc = AsyncCanonicalizer(_make_config())
        svc.emitter.on("tool.format_detected", capture)
        async with svc:
            await svc.detect_format(_anthropic_tool())

        assert detected == ["anthropic"]


class TestAsyncCanonicalizerConfidence:
    """confidence() method."""

    @pytest.mark.asyncio
    async def test_returns_all_formats(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            scores = await svc.confidence(_openai_tool())
            for fmt in SourceFormat:
                assert fmt in scores

    @pytest.mark.asyncio
    async def test_openai_scores_highest_for_openai_tool(self) -> None:
        async with AsyncCanonicalizer(_make_config()) as svc:
            scores = await svc.confidence(_openai_tool())
            assert scores[SourceFormat.openai] == 1.0

    @pytest.mark.asyncio
    async def test_raises_when_not_started(self) -> None:
        svc = AsyncCanonicalizer(_make_config())
        with pytest.raises(RuntimeError):
            await svc.confidence(_openai_tool())


# ===========================================================================
# 2. store.py — StoredTool and ToolStore
# ===========================================================================


class TestStoredToolFromCanonicalTool:
    """StoredTool.from_canonical_tool() conversion."""

    def test_name_is_copied(self) -> None:
        tool = _canonical_tool("my_tool")
        stored = StoredTool.from_canonical_tool(tool)
        assert stored.name == "my_tool"

    def test_source_format_is_string(self) -> None:
        tool = _canonical_tool()
        stored = StoredTool.from_canonical_tool(tool)
        assert stored.source_format == "openai"

    def test_canonical_json_is_valid_json(self) -> None:
        tool = _canonical_tool()
        stored = StoredTool.from_canonical_tool(tool)
        parsed = json.loads(stored.canonical_json)
        assert isinstance(parsed, dict)

    def test_capabilities_include_action_and_domain(self) -> None:
        tool = _canonical_tool(action="search", domain="web")
        stored = StoredTool.from_canonical_tool(tool)
        assert "search" in stored.capabilities
        assert "web" in stored.capabilities

    def test_side_effects_adds_side_effects_capability(self) -> None:
        tool = _canonical_tool(side_effects=True)
        stored = StoredTool.from_canonical_tool(tool)
        assert "side_effects" in stored.capabilities

    def test_security_tags_from_tool_security(self) -> None:
        tool = _canonical_tool(has_security=True)
        stored = StoredTool.from_canonical_tool(tool)
        assert "internet" in stored.security_tags

    def test_no_security_gives_empty_tags(self) -> None:
        tool = _canonical_tool(has_security=False)
        stored = StoredTool.from_canonical_tool(tool)
        assert stored.security_tags == []

    def test_pii_handling_creates_pii_tag(self) -> None:
        tool = _canonical_tool(has_security=False)
        tool = tool.model_copy(
            update={
                "security": ToolSecurity(
                    pii_handling="processes",
                    data_classification="public",
                )
            }
        )
        stored = StoredTool.from_canonical_tool(tool)
        assert "processes" in stored.pii_tags

    def test_roundtrip_to_canonical_tool(self) -> None:
        original = _canonical_tool("roundtrip_tool")
        stored = StoredTool.from_canonical_tool(original)
        restored = stored.to_canonical_tool()
        assert restored.name == original.name
        assert restored.description == original.description


class TestToolStoreCRUD:
    """ToolStore CRUD operations with in-memory backend."""

    @pytest.mark.asyncio
    async def test_save_and_get(self) -> None:
        async with ToolStore.memory() as ts:
            tool = _canonical_tool("test_tool")
            tool_id = await ts.save(tool)
            retrieved = await ts.get(tool_id)
            assert retrieved is not None
            assert retrieved.name == "test_tool"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        async with ToolStore.memory() as ts:
            result = await ts.get("nonexistent-id")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_removes_tool(self) -> None:
        async with ToolStore.memory() as ts:
            tool_id = await ts.save(_canonical_tool())
            assert await ts.delete(tool_id) is True
            assert await ts.get(tool_id) is None

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self) -> None:
        async with ToolStore.memory() as ts:
            result = await ts.delete("ghost-id")
            assert result is False

    @pytest.mark.asyncio
    async def test_count_increments_on_save(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool("t1"))
            await ts.save(_canonical_tool("t2"))
            assert await ts.count() == 2

    @pytest.mark.asyncio
    async def test_all_returns_saved_tools(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool("alpha"))
            await ts.save(_canonical_tool("beta"))
            all_tools = await ts.all()
            names = {t.name for t in all_tools}
            assert {"alpha", "beta"}.issubset(names)

    @pytest.mark.asyncio
    async def test_requires_initialization(self) -> None:
        ts = ToolStore.memory()
        with pytest.raises(RuntimeError, match="not been initialized"):
            await ts.save(_canonical_tool())


class TestToolStoreQueryMethods:
    """Semantic query methods on ToolStore."""

    @pytest.mark.asyncio
    async def test_find_by_capability(self) -> None:
        async with ToolStore.memory() as ts:
            search_tool = _canonical_tool("searcher", action="search", domain="web")
            write_tool = _canonical_tool("writer", action="write", domain="filesystem")
            await ts.save(search_tool)
            await ts.save(write_tool)

            results = await ts.find_by_capability("search")
            assert any(t.name == "searcher" for t in results)
            assert all(t.name != "writer" for t in results)

    @pytest.mark.asyncio
    async def test_find_by_capability_no_matches(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool())
            results = await ts.find_by_capability("nonexistent_cap")
            assert results == []

    @pytest.mark.asyncio
    async def test_find_by_security_tag(self) -> None:
        async with ToolStore.memory() as ts:
            # Tool with internet permission
            tool_with_internet = _canonical_tool(has_security=True)
            # Tool without security
            tool_without = _canonical_tool("bare", has_security=False)
            await ts.save(tool_with_internet)
            await ts.save(tool_without)

            internet_tools = await ts.find_by_security_tag("internet")
            assert any(t.name == "search_web" for t in internet_tools)

    @pytest.mark.asyncio
    async def test_find_by_pii_tag(self) -> None:
        async with ToolStore.memory() as ts:
            tool = _canonical_tool(has_security=False)
            tool_with_pii = tool.model_copy(
                update={
                    "security": ToolSecurity(pii_handling="processes"),
                    "name": "pii_tool",
                }
            )
            await ts.save(tool_with_pii)
            await ts.save(_canonical_tool("safe_tool", has_security=False))

            pii_results = await ts.find_by_pii_tag("processes")
            assert any(t.name == "pii_tool" for t in pii_results)
            assert all(t.name != "safe_tool" for t in pii_results)

    @pytest.mark.asyncio
    async def test_search_by_name_substring(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool("search_web"))
            await ts.save(_canonical_tool("search_images"))
            await ts.save(_canonical_tool("write_file"))

            results = await ts.search_by_name("search")
            names = {t.name for t in results}
            assert "search_web" in names
            assert "search_images" in names
            assert "write_file" not in names

    @pytest.mark.asyncio
    async def test_search_by_name_case_insensitive(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool("SearchWeb"))
            results = await ts.search_by_name("searchweb")
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_by_name_no_match(self) -> None:
        async with ToolStore.memory() as ts:
            await ts.save(_canonical_tool())
            results = await ts.search_by_name("zzz_no_match")
            assert results == []

    @pytest.mark.asyncio
    async def test_find_by_source_format(self) -> None:
        async with ToolStore.memory() as ts:
            openai_tool = _canonical_tool()
            mcp_tool = _canonical_tool("mcp_list")
            mcp_tool = mcp_tool.model_copy(
                update={"source_format": SourceFormat.mcp}
            )
            await ts.save(openai_tool)
            await ts.save(mcp_tool)

            openai_results = await ts.find_by_source_format(SourceFormat.openai)
            assert all(t.source_format == "openai" for t in openai_results)


# ===========================================================================
# 3. enricher.py — SchemaEnricher and EnrichmentResult
# ===========================================================================


class TestEnrichmentResult:
    """Pydantic model validation for EnrichmentResult."""

    def test_default_values(self) -> None:
        result = EnrichmentResult()
        assert result.capabilities == []
        assert result.security_tags == []
        assert result.pii_tags == []
        assert result.description_enhancement == ""
        assert result.confidence == 0.0

    def test_confidence_clipped_at_zero(self) -> None:
        with pytest.raises(Exception):
            EnrichmentResult(confidence=-0.1)

    def test_confidence_clipped_at_one(self) -> None:
        with pytest.raises(Exception):
            EnrichmentResult(confidence=1.1)

    def test_populated_result(self) -> None:
        result = EnrichmentResult(
            capabilities=["read", "filesystem"],
            security_tags=["filesystem_access"],
            pii_tags=["processes_user_data"],
            description_enhancement="Reads a file.",
            confidence=0.95,
        )
        assert "read" in result.capabilities
        assert "filesystem_access" in result.security_tags
        assert result.confidence == 0.95


class TestSchemaEnricherWithMock:
    """SchemaEnricher backed by MockProvider — no network calls."""

    @pytest.mark.asyncio
    async def test_enrich_returns_enrichment_result(self) -> None:
        enricher = SchemaEnricher.with_mock(responses=[_enrichment_json()])
        result = await enricher.enrich(_anthropic_tool())
        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_capabilities_parsed_correctly(self) -> None:
        response = _enrichment_json(capabilities=["read", "filesystem"])
        enricher = SchemaEnricher.with_mock(responses=[response])
        result = await enricher.enrich(_anthropic_tool())
        assert "read" in result.capabilities
        assert "filesystem" in result.capabilities

    @pytest.mark.asyncio
    async def test_security_tags_parsed(self) -> None:
        response = _enrichment_json(security_tags=["filesystem_access", "read_only"])
        enricher = SchemaEnricher.with_mock(responses=[response])
        result = await enricher.enrich(_anthropic_tool())
        assert "filesystem_access" in result.security_tags

    @pytest.mark.asyncio
    async def test_pii_tags_parsed(self) -> None:
        response = _enrichment_json(pii_tags=["processes_user_data"])
        enricher = SchemaEnricher.with_mock(responses=[response])
        result = await enricher.enrich(_openai_tool())
        assert "processes_user_data" in result.pii_tags

    @pytest.mark.asyncio
    async def test_description_enhancement_parsed(self) -> None:
        response = _enrichment_json(description_enhancement="Enhanced description.")
        enricher = SchemaEnricher.with_mock(responses=[response])
        result = await enricher.enrich(_openai_tool())
        assert result.description_enhancement == "Enhanced description."

    @pytest.mark.asyncio
    async def test_confidence_parsed(self) -> None:
        response = _enrichment_json(confidence=0.75)
        enricher = SchemaEnricher.with_mock(responses=[response])
        result = await enricher.enrich(_mcp_tool())
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_invalid_json_raises_enrichment_error(self) -> None:
        enricher = SchemaEnricher.with_mock(responses=["not valid json at all"])
        with pytest.raises(EnrichmentError):
            await enricher.enrich(_openai_tool())

    @pytest.mark.asyncio
    async def test_enrich_safe_returns_empty_on_failure(self) -> None:
        enricher = SchemaEnricher.with_mock(responses=["bad json {{{"])
        result = await enricher.enrich_safe(_openai_tool())
        assert isinstance(result, EnrichmentResult)
        assert result.capabilities == []
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_with_mock_factory_creates_valid_enricher(self) -> None:
        enricher = SchemaEnricher.with_mock()
        assert enricher is not None
        result = await enricher.enrich(_openai_tool())
        assert isinstance(result, EnrichmentResult)

    @pytest.mark.asyncio
    async def test_multiple_enrichments_cycle_responses(self) -> None:
        responses = [
            _enrichment_json(capabilities=["read"]),
            _enrichment_json(capabilities=["write"]),
        ]
        enricher = SchemaEnricher.with_mock(responses=responses)
        r1 = await enricher.enrich(_openai_tool())
        r2 = await enricher.enrich(_openai_tool())
        assert "read" in r1.capabilities
        assert "write" in r2.capabilities


# ===========================================================================
# 4. integration.py — ToolCanonIntegration and register_with_aumos
# ===========================================================================


class TestToolCanonIntegrationSetup:
    """Registration and teardown with AumOS."""

    @pytest.mark.asyncio
    async def test_setup_registers_service(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            service = hub.get_service("toolcanon")
            assert service is not None
            assert service.name == "toolcanon"
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_service_capabilities_advertised(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            service = hub.get_service("toolcanon")
            assert service is not None
            assert "tool_canonicalization" in service.capabilities
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_is_set_up_property(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            assert integration.is_set_up is False
            await integration.setup()
            assert integration.is_set_up is True
            await integration.teardown()
            assert integration.is_set_up is False

    @pytest.mark.asyncio
    async def test_setup_is_idempotent(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            await integration.setup()  # second call — no error
            services = hub.list_services()
            toolcanon_services = [s for s in services if s.name == "toolcanon"]
            assert len(toolcanon_services) == 1
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_teardown_unregisters_service(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            await integration.teardown()
            service = hub.get_service("toolcanon")
            assert service is None

    @pytest.mark.asyncio
    async def test_teardown_without_setup_is_safe(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.teardown()  # must not raise

    @pytest.mark.asyncio
    async def test_event_bus_property(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            assert integration.event_bus is hub.events

    @pytest.mark.asyncio
    async def test_hub_property(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            assert integration.hub is hub


class TestToolCanonIntegrationEvents:
    """Event subscription and publication."""

    @pytest.mark.asyncio
    async def test_subscribes_to_tool_registered_events(self) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            count = hub.events.subscriber_count("tool.registered")
            assert count >= 1
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_publish_canonicalized_event(self) -> None:
        received: list[Any] = []

        async def capture_event(event: Any) -> None:
            received.append(event)

        async with AumOS() as hub:
            hub.events.subscribe("tool.canonicalized", capture_event)
            integration = ToolCanonIntegration(hub)
            await integration.setup()

            from aumai_toolcanon.core import Canonicalizer

            result = Canonicalizer().canonicalize(_openai_tool())
            await integration.publish_canonicalized(result)

            assert len(received) == 1
            assert received[0].event_type == "tool.canonicalized"
            assert received[0].data["tool_name"] == "search_web"
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_tool_registered_event_triggers_canonicalization(self) -> None:
        published: list[Any] = []

        async def capture_canonicalized(event: Any) -> None:
            published.append(event)

        async with AumOS() as hub:
            hub.events.subscribe("tool.canonicalized", capture_canonicalized)
            integration = ToolCanonIntegration(hub)
            await integration.setup()

            # Publish a tool.registered event — should trigger auto-canonicalization
            await hub.events.publish_simple(
                "tool.registered",
                source="external_service",
                tool_def=_openai_tool(),
            )

            # Give the event loop a chance to process
            import asyncio

            await asyncio.sleep(0.01)

            assert len(published) >= 1
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_tool_registered_without_tool_def_is_handled_gracefully(
        self,
    ) -> None:
        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
            # Publish without tool_def — should not raise
            await hub.events.publish_simple(
                "tool.registered",
                source="external_service",
            )
            import asyncio

            await asyncio.sleep(0.01)
            await integration.teardown()


class TestRegisterWithAumOS:
    """register_with_aumos() convenience factory."""

    @pytest.mark.asyncio
    async def test_returns_set_up_integration(self) -> None:
        async with AumOS() as hub:
            integration = await register_with_aumos(hub)
            assert integration.is_set_up is True
            assert hub.get_service("toolcanon") is not None
            await integration.teardown()

    @pytest.mark.asyncio
    async def test_uses_singleton_hub_when_none_provided(self) -> None:
        AumOS.reset()
        integration = await register_with_aumos()
        assert integration.is_set_up is True
        await integration.teardown()
        AumOS.reset()
