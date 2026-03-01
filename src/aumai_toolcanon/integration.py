"""AumOS integration for aumai-toolcanon.

Registers the ``toolcanon`` service with the AumOS integration hub and wires
up event publishing/subscription so that canonical tool events flow through the
shared :class:`~aumai_integration.eventbus.EventBus`.

Key responsibilities
--------------------
1. Register ``toolcanon`` as a :class:`~aumai_integration.models.ServiceInfo`.
2. Publish ``"tool.canonicalized"`` events to the AumOS event bus whenever
   the :class:`~aumai_toolcanon.async_core.AsyncCanonicalizer` emits them.
3. Subscribe to ``"tool.registered"`` events from external services so that
   new tool definitions are automatically canonicalized.

Usage::

    from aumai_integration import AumOS
    from aumai_toolcanon.integration import ToolCanonIntegration

    async with AumOS() as hub:
        integration = ToolCanonIntegration(hub)
        await integration.setup()
        # Now publish events through the hub as usual
        await hub.events.publish_simple("tool.registered", source="my_service",
                                        tool_def={"name": "my_tool", ...})
"""

from __future__ import annotations

import logging
from typing import Any

from aumai_integration import AumOS, Event, EventBus
from aumai_integration.models import ServiceInfo

from aumai_toolcanon import __version__
from aumai_toolcanon.async_core import AsyncCanonicalizer
from aumai_toolcanon.models import CanonicalTool, CanonicalizationResult

logger = logging.getLogger(__name__)

_SERVICE_NAME = "toolcanon"
_SERVICE_DESCRIPTION = (
    "Normalize tool definitions from any supported format "
    "(OpenAI, Anthropic, MCP, LangChain) to the AumAI Tool Canonical IR "
    "with unique semantic metadata."
)
_SERVICE_CAPABILITIES = [
    "tool_canonicalization",
    "format_detection",
    "semantic_metadata",
    "pii_detection",
    "security_tagging",
]


def _build_service_info() -> ServiceInfo:
    """Build the :class:`~aumai_integration.models.ServiceInfo` descriptor for toolcanon.

    Returns:
        A fully-populated :class:`~aumai_integration.models.ServiceInfo`.
    """
    return ServiceInfo(
        name=_SERVICE_NAME,
        version=__version__,
        description=_SERVICE_DESCRIPTION,
        capabilities=_SERVICE_CAPABILITIES,
        endpoints={},
        metadata={
            "supported_formats": ["openai", "anthropic", "mcp", "langchain", "raw"],
            "output_formats": ["openai", "anthropic", "mcp", "json-schema"],
        },
        status="healthy",
    )


class ToolCanonIntegration:
    """Integration adapter that registers toolcanon with AumOS.

    Wires :class:`~aumai_toolcanon.async_core.AsyncCanonicalizer` events to the
    AumOS :class:`~aumai_integration.eventbus.EventBus` and subscribes to
    incoming ``"tool.registered"`` events so that new tool definitions are
    automatically canonicalized and re-published as ``"tool.canonicalized"``.

    Args:
        hub: The :class:`~aumai_integration.core.AumOS` integration hub.
        canonicalizer: Optional pre-configured
            :class:`~aumai_toolcanon.async_core.AsyncCanonicalizer`.  If
            ``None`` a default one is created internally.

    Example::

        async with AumOS() as hub:
            integration = ToolCanonIntegration(hub)
            await integration.setup()
    """

    def __init__(
        self,
        hub: AumOS,
        canonicalizer: AsyncCanonicalizer | None = None,
    ) -> None:
        self._hub = hub
        self._canonicalizer = canonicalizer
        self._subscription_id: str | None = None
        self._is_set_up: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Register the service with AumOS and subscribe to integration events.

        Idempotent — calling this multiple times is safe.

        After setup:
        - The ``toolcanon`` service is visible in :meth:`~aumai_integration.core.AumOS.list_services`.
        - The event bus is wired to forward ``"tool.registered"`` events to the
          canonicalizer and re-publish results as ``"tool.canonicalized"``.
        """
        if self._is_set_up:
            return

        # 1. Register service descriptor
        service_info = _build_service_info()
        self._hub.register(service_info)
        logger.info(
            "ToolCanon: registered service %r v%s with AumOS",
            _SERVICE_NAME,
            __version__,
        )

        # 2. Subscribe to "tool.registered" events
        self._subscription_id = self._hub.events.subscribe(
            pattern="tool.registered",
            handler=self._on_tool_registered,
            subscriber=_SERVICE_NAME,
        )
        logger.info(
            "ToolCanon: subscribed to 'tool.registered' events (id=%s)",
            self._subscription_id,
        )

        self._is_set_up = True

    async def teardown(self) -> None:
        """Unregister from AumOS and remove event subscriptions.

        Idempotent — safe to call even if :meth:`setup` was never called.
        """
        if not self._is_set_up:
            return

        if self._subscription_id is not None:
            removed = self._hub.events.unsubscribe(self._subscription_id)
            if removed:
                logger.info(
                    "ToolCanon: unsubscribed from events (id=%s)",
                    self._subscription_id,
                )
            self._subscription_id = None

        self._hub.unregister(_SERVICE_NAME)
        logger.info("ToolCanon: unregistered from AumOS")
        self._is_set_up = False

    async def publish_canonicalized(
        self,
        result: CanonicalizationResult,
    ) -> int:
        """Publish a ``"tool.canonicalized"`` event to the AumOS event bus.

        Args:
            result: The :class:`~aumai_toolcanon.models.CanonicalizationResult`
                to publish.

        Returns:
            The number of event handlers that received the event.
        """
        return await self._hub.events.publish_simple(
            "tool.canonicalized",
            source=_SERVICE_NAME,
            tool_name=result.tool.name,
            source_format=result.source_format_detected.value,
            warning_count=len(result.warnings),
            warnings=result.warnings,
            canonical_tool=result.tool.model_dump(mode="json"),
        )

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    async def _on_tool_registered(self, event: Event) -> None:
        """Handle an incoming ``"tool.registered"`` event.

        Extracts ``tool_def`` from ``event.data``, canonicalizes it, and
        publishes the result as ``"tool.canonicalized"`` on the bus.

        Args:
            event: The incoming :class:`~aumai_integration.models.Event`.
        """
        tool_def: Any = event.data.get("tool_def")
        if not isinstance(tool_def, dict):
            logger.warning(
                "ToolCanon: received 'tool.registered' event from %r "
                "but 'tool_def' is missing or not a dict — skipping.",
                event.source,
            )
            return

        canonicalizer = self._get_or_create_canonicalizer()

        try:
            if canonicalizer.status.state == "running":
                result = await canonicalizer.canonicalize(tool_def)
            else:
                # Fall back to synchronous canonicalization if the async
                # service is not running (e.g. during integration testing).
                from aumai_toolcanon.core import Canonicalizer

                sync_canon = Canonicalizer()
                result = sync_canon.canonicalize(tool_def)

            await self.publish_canonicalized(result)
            logger.info(
                "ToolCanon: canonicalized tool %r (format=%s, warnings=%d)",
                result.tool.name,
                result.source_format_detected.value,
                len(result.warnings),
            )
        except Exception as exc:
            logger.error(
                "ToolCanon: failed to canonicalize tool from event %r: %s",
                event.event_id,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_set_up(self) -> bool:
        """``True`` after :meth:`setup` has been called successfully."""
        return self._is_set_up

    @property
    def hub(self) -> AumOS:
        """The :class:`~aumai_integration.core.AumOS` hub this integration is wired to."""
        return self._hub

    @property
    def event_bus(self) -> EventBus:
        """Convenience accessor for the hub's :class:`~aumai_integration.eventbus.EventBus`."""
        return self._hub.events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_canonicalizer(self) -> AsyncCanonicalizer:
        """Return the canonicalizer, creating a default one if needed.

        Returns:
            The :class:`~aumai_toolcanon.async_core.AsyncCanonicalizer` in use.
        """
        if self._canonicalizer is None:
            from aumai_async_core import AsyncServiceConfig

            config = AsyncServiceConfig(
                name="toolcanon-integration",
                health_check_interval_seconds=0,
            )
            self._canonicalizer = AsyncCanonicalizer(config)
        return self._canonicalizer


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


async def register_with_aumos(
    hub: AumOS | None = None,
    canonicalizer: AsyncCanonicalizer | None = None,
) -> ToolCanonIntegration:
    """Register the toolcanon service with AumOS and return the integration.

    This is the recommended entry point for integrating toolcanon into a
    running AumOS hub.

    Args:
        hub: The :class:`~aumai_integration.core.AumOS` hub.  Defaults to
            ``AumOS.instance()`` (the module-level singleton).
        canonicalizer: Optional pre-configured
            :class:`~aumai_toolcanon.async_core.AsyncCanonicalizer`.

    Returns:
        The configured and set-up :class:`ToolCanonIntegration`.

    Example::

        from aumai_integration import AumOS
        from aumai_toolcanon.integration import register_with_aumos

        async with AumOS() as hub:
            integration = await register_with_aumos(hub)
    """
    effective_hub: AumOS = hub if hub is not None else AumOS.instance()
    integration = ToolCanonIntegration(effective_hub, canonicalizer=canonicalizer)
    await integration.setup()
    return integration


__all__ = [
    "ToolCanonIntegration",
    "register_with_aumos",
]
