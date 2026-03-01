"""Async API for aumai-toolcanon — AsyncCanonicalizer extending AsyncService.

Wraps the synchronous :class:`~aumai_toolcanon.core.Canonicalizer` and
:class:`~aumai_toolcanon.core.FormatDetector` in an async-safe, lifecycle-
managed service that emits events through
:class:`~aumai_async_core.events.AsyncEventEmitter` on every successful
canonicalization.

Usage::

    config = AsyncServiceConfig(name="toolcanon-async")
    async with AsyncCanonicalizer(config) as service:
        result = await service.canonicalize(tool_def)
        print(result.tool.name)
"""

from __future__ import annotations

from typing import Any

from aumai_async_core import AsyncEventEmitter, AsyncService, AsyncServiceConfig

from aumai_toolcanon.core import Canonicalizer, FormatDetector
from aumai_toolcanon.models import (
    CanonicalizationResult,
    SourceFormat,
)


class AsyncCanonicalizer(AsyncService):
    """Async wrapper around :class:`~aumai_toolcanon.core.Canonicalizer`.

    Provides lifecycle management via :class:`~aumai_async_core.core.AsyncService`
    and emits ``"tool.canonicalized"`` events through an internal
    :class:`~aumai_async_core.events.AsyncEventEmitter` after each successful
    canonicalization.

    The internal :class:`~aumai_toolcanon.core.Canonicalizer` and
    :class:`~aumai_toolcanon.core.FormatDetector` are instantiated during
    :meth:`on_start` and released during :meth:`on_stop`.

    Args:
        config: Service configuration supplied to the parent
            :class:`~aumai_async_core.core.AsyncService`.
        emitter: Optional external emitter to receive events.  If ``None``
            a new :class:`~aumai_async_core.events.AsyncEventEmitter` is
            created for this service instance.

    Example::

        config = AsyncServiceConfig(name="toolcanon", health_check_interval_seconds=0)
        async with AsyncCanonicalizer(config) as service:
            result = await service.canonicalize({"name": "my_tool", ...})
    """

    def __init__(
        self,
        config: AsyncServiceConfig,
        emitter: AsyncEventEmitter | None = None,
    ) -> None:
        super().__init__(config)
        self._emitter: AsyncEventEmitter = emitter or AsyncEventEmitter()
        self._canonicalizer: Canonicalizer | None = None
        self._detector: FormatDetector | None = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def on_start(self) -> None:
        """Instantiate the underlying canonicalizer and detector."""
        self._canonicalizer = Canonicalizer()
        self._detector = FormatDetector()

    async def on_stop(self) -> None:
        """Release references to the canonicalizer and detector."""
        self._canonicalizer = None
        self._detector = None

    async def health_check(self) -> bool:
        """Return ``True`` if the service is running and the canonicalizer is ready."""
        return self._canonicalizer is not None and self._detector is not None

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def canonicalize(
        self,
        tool_def: dict[str, Any],
        source_format: SourceFormat | None = None,
    ) -> CanonicalizationResult:
        """Canonicalize *tool_def* asynchronously and emit a ``tool.canonicalized`` event.

        Args:
            tool_def: Raw tool definition dictionary from any supported format.
            source_format: Override auto-detection by supplying the format explicitly.

        Returns:
            A :class:`~aumai_toolcanon.models.CanonicalizationResult` containing
            the canonical tool, any warnings, and the detected source format.

        Raises:
            RuntimeError: If the service has not been started yet (call
                ``await service.start()`` or use it as an async context manager).
        """
        if self._canonicalizer is None:
            raise RuntimeError(
                "AsyncCanonicalizer is not running. "
                "Call await service.start() or use it as an async context manager."
            )

        await self.increment_request_count()
        result: CanonicalizationResult = self._canonicalizer.canonicalize(
            tool_def, source_format
        )

        await self._emitter.emit(
            "tool.canonicalized",
            tool_name=result.tool.name,
            source_format=result.source_format_detected.value,
            warning_count=len(result.warnings),
            result=result,
        )

        return result

    async def detect_format(self, tool_def: dict[str, Any]) -> SourceFormat:
        """Detect the source format of *tool_def* without full canonicalization.

        Args:
            tool_def: Raw tool definition dictionary to inspect.

        Returns:
            The detected :class:`~aumai_toolcanon.models.SourceFormat`.

        Raises:
            RuntimeError: If the service has not been started yet.
        """
        if self._detector is None:
            raise RuntimeError(
                "AsyncCanonicalizer is not running. "
                "Call await service.start() or use it as an async context manager."
            )

        detected: SourceFormat = self._detector.detect(tool_def)
        await self._emitter.emit(
            "tool.format_detected",
            source_format=detected.value,
        )
        return detected

    async def confidence(
        self, tool_def: dict[str, Any]
    ) -> dict[SourceFormat, float]:
        """Return format-confidence scores for *tool_def*.

        Args:
            tool_def: Raw tool definition dictionary.

        Returns:
            Mapping from :class:`~aumai_toolcanon.models.SourceFormat` to
            confidence score (0.0–1.0).

        Raises:
            RuntimeError: If the service has not been started yet.
        """
        if self._detector is None:
            raise RuntimeError(
                "AsyncCanonicalizer is not running. "
                "Call await service.start() or use it as an async context manager."
            )
        return self._detector.confidence(tool_def)

    # ------------------------------------------------------------------
    # Event emitter access
    # ------------------------------------------------------------------

    @property
    def emitter(self) -> AsyncEventEmitter:
        """The :class:`~aumai_async_core.events.AsyncEventEmitter` for this service.

        Returns:
            The emitter instance.  External code may register handlers via
            ``service.emitter.on("tool.canonicalized", handler)``.
        """
        return self._emitter


__all__ = ["AsyncCanonicalizer"]
