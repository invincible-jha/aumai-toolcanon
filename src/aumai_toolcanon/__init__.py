"""aumai-toolcanon: Normalize tool definitions to the AumAI Tool Canonical IR."""

from aumai_toolcanon.models import (
    CanonicalizationResult,
    CanonicalTool,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)

__version__ = "0.1.0"

__all__ = [
    # Original public API (unchanged)
    "CanonicalTool",
    "CanonicalizationResult",
    "SourceFormat",
    "ToolCapability",
    "ToolSecurity",
    # Foundation-library extensions (lazy import — avoids hard dependency
    # errors in environments where the foundation libraries are not installed)
    "AsyncCanonicalizer",
    "StoredTool",
    "ToolStore",
    "EnrichmentResult",
    "EnrichmentError",
    "SchemaEnricher",
    "ToolCanonIntegration",
    "register_with_aumos",
]


def __getattr__(name: str) -> object:
    """Lazy-load foundation-library classes to avoid import errors when the
    corresponding optional dependency is not installed.

    Args:
        name: Attribute name being accessed.

    Returns:
        The requested class or object.

    Raises:
        AttributeError: If *name* is not a known lazy export.
    """
    if name == "AsyncCanonicalizer":
        from aumai_toolcanon.async_core import AsyncCanonicalizer

        return AsyncCanonicalizer

    if name in ("StoredTool", "ToolStore"):
        from aumai_toolcanon import store as _store_module

        return getattr(_store_module, name)

    if name in ("EnrichmentResult", "EnrichmentError", "SchemaEnricher"):
        from aumai_toolcanon import enricher as _enricher_module

        return getattr(_enricher_module, name)

    if name in ("ToolCanonIntegration", "register_with_aumos"):
        from aumai_toolcanon import integration as _integration_module

        return getattr(_integration_module, name)

    raise AttributeError(f"module 'aumai_toolcanon' has no attribute {name!r}")
