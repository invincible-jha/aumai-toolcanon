"""Persistence layer for canonical tool definitions via aumai-store.

:class:`ToolStore` wraps an :class:`~aumai_store.core.Store` to provide a
high-level CRUD interface specifically for :class:`StoredTool` records.  It
adds semantic query methods beyond the generic repository:

- :meth:`find_by_capability` — equality match on the ``capabilities`` JSON column
- :meth:`find_by_security_tag` — search within the ``security_tags`` list
- :meth:`search_by_name` — substring/prefix search on the tool name

:class:`StoredTool` is a Pydantic model whose ``canonical_json``,
``capabilities``, ``security_tags``, and ``pii_tags`` fields are stored as
serialized JSON in the backing SQLite table (handled transparently by
:class:`~aumai_store.repository.Repository`).

Usage::

    async with ToolStore.memory() as ts:
        stored_id = await ts.save(tool)
        retrieved = await ts.get(stored_id)
        web_tools = await ts.find_by_capability("search")
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aumai_store import Repository, Store

from aumai_toolcanon.models import CanonicalTool, SourceFormat


# ---------------------------------------------------------------------------
# StoredTool model
# ---------------------------------------------------------------------------


class StoredTool(BaseModel):
    """Persisted representation of a canonical tool definition.

    Attributes:
        id: Primary key — a UUID string generated on first save.
        name: The tool name (mirrors :attr:`~aumai_toolcanon.models.CanonicalTool.name`).
        source_format: The original source format as a string enum value.
        canonical_json: Full JSON serialization of the
            :class:`~aumai_toolcanon.models.CanonicalTool` instance.
        capabilities: List of capability strings extracted from the tool
            (e.g. ``["read", "filesystem"]``).
        security_tags: Security-relevant tags derived from the tool's
            :class:`~aumai_toolcanon.models.ToolSecurity` metadata.
        pii_tags: PII handling tags derived from the tool's security metadata.
        created_at: ISO-8601 UTC timestamp string assigned at persistence time.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    source_format: str
    canonical_json: str
    capabilities: list[str] = Field(default_factory=list)
    security_tags: list[str] = Field(default_factory=list)
    pii_tags: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_canonical_tool(self) -> CanonicalTool:
        """Deserialize ``canonical_json`` back to a :class:`~aumai_toolcanon.models.CanonicalTool`.

        Returns:
            The reconstructed :class:`~aumai_toolcanon.models.CanonicalTool`.
        """
        data: dict[str, Any] = json.loads(self.canonical_json)
        return CanonicalTool.model_validate(data)

    @classmethod
    def from_canonical_tool(
        cls,
        tool: CanonicalTool,
        extra_capabilities: list[str] | None = None,
        extra_security_tags: list[str] | None = None,
        extra_pii_tags: list[str] | None = None,
    ) -> "StoredTool":
        """Construct a :class:`StoredTool` from a :class:`~aumai_toolcanon.models.CanonicalTool`.

        Capability strings are derived from the tool's
        :class:`~aumai_toolcanon.models.ToolCapability`:
        the ``action``, the ``domain``, and ``"side_effects"`` when present.
        Security and PII tags are derived from
        :class:`~aumai_toolcanon.models.ToolSecurity` when present.

        Args:
            tool: The :class:`~aumai_toolcanon.models.CanonicalTool` to persist.
            extra_capabilities: Additional capability strings to merge in.
            extra_security_tags: Additional security tags to merge in.
            extra_pii_tags: Additional PII tags to merge in.

        Returns:
            A new :class:`StoredTool` instance ready for persistence.
        """
        capabilities: list[str] = []
        if tool.capabilities.action:
            capabilities.append(tool.capabilities.action)
        if tool.capabilities.domain:
            capabilities.append(tool.capabilities.domain)
        if tool.capabilities.side_effects:
            capabilities.append("side_effects")
        if extra_capabilities:
            capabilities.extend(extra_capabilities)

        security_tags: list[str] = []
        pii_tags: list[str] = []
        if tool.security is not None:
            security_tags.extend(tool.security.required_permissions)
            if tool.security.data_classification not in ("public", ""):
                security_tags.append(tool.security.data_classification)
            if tool.security.pii_handling not in ("none", ""):
                pii_tags.append(tool.security.pii_handling)
        if extra_security_tags:
            security_tags.extend(extra_security_tags)
        if extra_pii_tags:
            pii_tags.extend(extra_pii_tags)

        return cls(
            name=tool.name,
            source_format=tool.source_format.value,
            canonical_json=tool.model_dump_json(),
            capabilities=capabilities,
            security_tags=security_tags,
            pii_tags=pii_tags,
        )


# ---------------------------------------------------------------------------
# ToolStore
# ---------------------------------------------------------------------------


class ToolStore:
    """High-level store for persisting :class:`StoredTool` instances.

    Wraps an :class:`~aumai_store.core.Store` and provides semantic query
    methods on top of the generic :class:`~aumai_store.repository.Repository`.

    The backing table is created automatically on :meth:`initialize`.

    Example (in-memory, ideal for tests)::

        async with ToolStore.memory() as ts:
            stored_id = await ts.save(tool)
            found = await ts.find_by_capability("read")

    Example (SQLite)::

        async with ToolStore.sqlite("tools.db") as ts:
            stored_id = await ts.save(tool)

    Args:
        store: An :class:`~aumai_store.core.Store` instance to delegate to.
    """

    _TABLE_NAME = "stored_tool"

    def __init__(self, store: Store) -> None:
        self._store = store
        self._repo: Repository[StoredTool] | None = None

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def memory(cls) -> "ToolStore":
        """Create a :class:`ToolStore` backed by an in-memory :class:`~aumai_store.core.Store`.

        Suitable for unit tests.  All data is lost when the store is closed.

        Returns:
            A new :class:`ToolStore` backed by :class:`~aumai_store.backends.MemoryBackend`.
        """
        return cls(Store.memory())

    @classmethod
    def sqlite(cls, path: str = "toolcanon.db") -> "ToolStore":
        """Create a :class:`ToolStore` backed by a SQLite file.

        Args:
            path: File-system path for the SQLite database.

        Returns:
            A new :class:`ToolStore` backed by :class:`~aumai_store.backends.SQLiteBackend`.
        """
        return cls(Store.sqlite(path))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the underlying store and ensure the ``stored_tool`` table exists.

        Must be called before any data operations.  Idempotent after the first
        call.
        """
        await self._store.initialize()
        self._repo = await self._store.prepare_repository(
            StoredTool, table_name=self._TABLE_NAME
        )

    async def close(self) -> None:
        """Release the underlying store connection."""
        await self._store.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ToolStore":
        """Initialize the store and return *self*."""
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the store on context exit."""
        await self.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, tool: CanonicalTool) -> str:
        """Persist a :class:`~aumai_toolcanon.models.CanonicalTool`.

        Converts the tool to a :class:`StoredTool` automatically before saving.

        Args:
            tool: The canonical tool to persist.

        Returns:
            The assigned row id (UUID string).

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        repo = self._require_repo()
        stored = StoredTool.from_canonical_tool(tool)
        return await repo.save(stored)

    async def get(self, tool_id: str) -> StoredTool | None:
        """Retrieve a :class:`StoredTool` by primary key.

        Args:
            tool_id: Row identifier returned by :meth:`save`.

        Returns:
            The :class:`StoredTool`, or ``None`` if not found.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        return await self._require_repo().get(tool_id)

    async def delete(self, tool_id: str) -> bool:
        """Delete a stored tool by primary key.

        Args:
            tool_id: Row identifier.

        Returns:
            ``True`` if the row existed and was deleted.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        return await self._require_repo().delete(tool_id)

    async def all(self, limit: int = 100, offset: int = 0) -> list[StoredTool]:
        """Return all persisted tools with pagination.

        Args:
            limit: Maximum number of tools to return.
            offset: Number of rows to skip.

        Returns:
            List of :class:`StoredTool` instances.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        return await self._require_repo().all(limit=limit, offset=offset)

    async def count(self) -> int:
        """Return the total number of persisted tools.

        Returns:
            Row count.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        return await self._require_repo().count()

    # ------------------------------------------------------------------
    # Semantic query methods
    # ------------------------------------------------------------------

    async def find_by_capability(self, capability: str) -> list[StoredTool]:
        """Find tools whose capability list contains *capability*.

        The search is case-sensitive substring match against the JSON-serialized
        ``capabilities`` column.  Because aumai-store serializes lists as JSON
        strings, this performs a scan over all rows and filters in Python.

        Args:
            capability: Capability string to search for (e.g. ``"read"``,
                ``"filesystem"``, ``"side_effects"``).

        Returns:
            List of :class:`StoredTool` instances whose capabilities include
            *capability*.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        all_tools = await self.all(limit=10_000)
        return [
            tool for tool in all_tools if capability in tool.capabilities
        ]

    async def find_by_security_tag(self, tag: str) -> list[StoredTool]:
        """Find tools whose security_tags list contains *tag*.

        Args:
            tag: Security tag to search for (e.g. ``"internet"``,
                ``"confidential"``).

        Returns:
            List of :class:`StoredTool` instances carrying *tag*.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        all_tools = await self.all(limit=10_000)
        return [tool for tool in all_tools if tag in tool.security_tags]

    async def find_by_pii_tag(self, tag: str) -> list[StoredTool]:
        """Find tools whose pii_tags list contains *tag*.

        Args:
            tag: PII tag to search for (e.g. ``"processes"``, ``"stores"``).

        Returns:
            List of matching :class:`StoredTool` instances.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        all_tools = await self.all(limit=10_000)
        return [tool for tool in all_tools if tag in tool.pii_tags]

    async def search_by_name(self, query: str) -> list[StoredTool]:
        """Find tools whose name contains *query* (case-insensitive substring match).

        Scans all rows and filters in Python to provide full-text-like search
        without requiring a separate FTS index.

        Args:
            query: Substring to match against tool names.

        Returns:
            List of :class:`StoredTool` instances whose name contains *query*.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        lower_query = query.lower()
        all_tools = await self.all(limit=10_000)
        return [
            tool for tool in all_tools if lower_query in tool.name.lower()
        ]

    async def find_by_source_format(
        self, source_format: SourceFormat
    ) -> list[StoredTool]:
        """Find tools that originated from *source_format*.

        Args:
            source_format: The :class:`~aumai_toolcanon.models.SourceFormat`
                to filter by.

        Returns:
            List of :class:`StoredTool` instances from *source_format*.

        Raises:
            RuntimeError: If the store has not been initialized.
        """
        return await self._require_repo().find(
            source_format=source_format.value
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_repo(self) -> Repository[StoredTool]:
        """Return the repository, raising if the store has not been initialized.

        Returns:
            The :class:`~aumai_store.repository.Repository` for
            :class:`StoredTool`.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if self._repo is None:
            raise RuntimeError(
                "ToolStore has not been initialized. "
                "Call await store.initialize() or use it as an async context manager."
            )
        return self._repo


__all__ = ["StoredTool", "ToolStore"]
