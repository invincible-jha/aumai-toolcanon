# API Reference — aumai-toolcanon

Complete reference for all public classes, functions, and Pydantic models in `aumai-toolcanon`.

---

## Module `aumai_toolcanon.models`

All data models. Import directly from the package root:

```python
from aumai_toolcanon import (
    CanonicalTool,
    CanonicalizationResult,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)
```

---

### `SourceFormat`

```python
class SourceFormat(str, Enum):
```

Enumeration of all supported tool definition source formats.

| Member | Value | Description |
|--------|-------|-------------|
| `openai` | `"openai"` | OpenAI function calling format (wrapped or legacy) |
| `anthropic` | `"anthropic"` | Anthropic tool use format |
| `mcp` | `"mcp"` | Model Context Protocol (MCP) tool format |
| `langchain` | `"langchain"` | LangChain tool schema format |
| `raw` | `"raw"` | Unknown or unrecognized format — best-effort passthrough |

**Example:**

```python
from aumai_toolcanon.models import SourceFormat

fmt = SourceFormat.openai
print(fmt.value)   # "openai"
print(fmt == "openai")  # True (SourceFormat is a str subclass)
```

---

### `ToolCapability`

```python
class ToolCapability(BaseModel):
```

Semantic capability metadata for a canonical tool. All fields have defaults, so you can construct this with zero arguments and fill in only what you know.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | `str` | `""` | Primary action verb: `read`, `write`, `search`, `call`, `delete`, `fetch`, `list`, `query`, etc. |
| `domain` | `str` | `""` | Domain the tool operates in: `filesystem`, `web`, `database`, `code`, `email`, `general` |
| `side_effects` | `bool` | `False` | `True` if the tool modifies external state (writes, deletes, sends) |
| `idempotent` | `bool` | `True` | `True` if calling the tool multiple times with the same inputs produces the same result |
| `cost_estimate` | `str` | `"unknown"` | Cost category: `free`, `low`, `medium`, `high`, `unknown` |

**Example:**

```python
from aumai_toolcanon.models import ToolCapability

cap = ToolCapability(
    action="search",
    domain="web",
    side_effects=False,
    idempotent=True,
    cost_estimate="low",
)
```

---

### `ToolSecurity`

```python
class ToolSecurity(BaseModel):
```

Security and data handling metadata for a canonical tool. Optional — attach to tools that require access control or data governance.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `required_permissions` | `list[str]` | `[]` | Permission strings that must be granted to invoke this tool |
| `data_classification` | `str` | `"public"` | Data sensitivity level: `public`, `internal`, `confidential`, `restricted` |
| `pii_handling` | `str` | `"none"` | How this tool handles personally identifiable information: `none`, `processes`, `stores`, `anonymizes` |

**Example:**

```python
from aumai_toolcanon.models import ToolSecurity

sec = ToolSecurity(
    required_permissions=["db:read", "records:query"],
    data_classification="confidential",
    pii_handling="processes",
)
```

---

### `CanonicalTool`

```python
class CanonicalTool(BaseModel):
```

The AumAI Tool Canonical Intermediate Representation (IR). This is the central data model of the entire library — every parser produces a `CanonicalTool`, and every emitter consumes one.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Normalized tool name |
| `version` | `str` | `"1.0.0"` | Semantic version of this tool definition |
| `description` | `str` | `""` | Human-readable description of what the tool does |
| `capabilities` | `ToolCapability` | `ToolCapability()` | Semantic capability metadata |
| `inputs` | `dict[str, Any]` | `{}` | JSON Schema object describing the tool's input parameters |
| `outputs` | `dict[str, Any]` | `{}` | JSON Schema object describing the tool's output (optional) |
| `security` | `ToolSecurity \| None` | `None` | Security and data handling metadata |
| `source_format` | `SourceFormat` | `SourceFormat.raw` | Which format this tool was parsed from |
| `original_definition` | `dict[str, Any]` | `{}` | Preserved verbatim copy of the original input definition |

**Example:**

```python
from aumai_toolcanon.models import CanonicalTool, ToolCapability, SourceFormat

tool = CanonicalTool(
    name="list_files",
    description="List all files in a directory",
    capabilities=ToolCapability(
        action="list",
        domain="filesystem",
        side_effects=False,
        idempotent=True,
        cost_estimate="free",
    ),
    inputs={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Absolute path to the directory"
            }
        },
        "required": ["directory"]
    },
    source_format=SourceFormat.openai,
)

# Pydantic serialization
tool_dict = tool.model_dump()
tool_json = tool.model_dump_json(indent=2)

# Round-trip from dict
reconstructed = CanonicalTool.model_validate(tool_dict)
```

---

### `CanonicalizationResult`

```python
class CanonicalizationResult(BaseModel):
```

The output of `Canonicalizer.canonicalize()`. Always contains a canonical tool, even if parsing encountered errors (in which case warnings describe what went wrong).

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `CanonicalTool` | The normalized canonical tool |
| `warnings` | `list[str]` | Non-fatal advisory messages (empty list if all is well) |
| `source_format_detected` | `SourceFormat` | The format that was detected or provided |

**Common warning messages:**

| Warning | Cause |
|---------|-------|
| `"Tool has no name"` | Input had no detectable name field |
| `"Tool has no description"` | Input had no description field |
| `"Could not detect source format; using raw passthrough."` | No parser matched — raw heuristic used |
| `"Parser error for openai: ..."` | The detected parser raised an exception; raw fallback was used |
| `"No parser for 'raw' format; extracted fields by heuristic."` | Explicit `source_format=raw` was passed |

**Example:**

```python
result = canon.canonicalize(tool_def)

if result.warnings:
    for warning in result.warnings:
        print(f"WARNING: {warning}")

tool = result.tool
print(tool.name)
```

---

## Module `aumai_toolcanon.core`

The two main engine classes. Import from the submodule:

```python
from aumai_toolcanon.core import FormatDetector, Canonicalizer
```

---

### `FormatDetector`

```python
class FormatDetector:
```

Auto-detects the source format of a tool definition dict by examining its structural signals. Instantiate once and reuse for many inputs.

#### Constructor

```python
def __init__(self) -> None:
```

Initializes all four format parsers internally. No configuration required.

#### Methods

---

##### `detect`

```python
def detect(self, tool_def: dict[str, Any]) -> SourceFormat:
```

Return the most likely `SourceFormat` for the given tool definition dict.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_def` | `dict[str, Any]` | The raw tool definition to inspect |

**Returns:** `SourceFormat` — the detected format, or `SourceFormat.raw` if none matched.

**Detection priority:**

1. `SourceFormat.openai` — `type == "function"` wrapper present, or `"name"` + `"parameters"` keys exist
2. `SourceFormat.anthropic` — `"name"` + `"input_schema"` keys present
3. `SourceFormat.mcp` — `"name"` + `"inputSchema"` keys present
4. `SourceFormat.langchain` — `"args_schema"`, `"schema"`, or `"properties"` + `"name"` present
5. `SourceFormat.raw` — fallback

**Example:**

```python
from aumai_toolcanon.core import FormatDetector

detector = FormatDetector()
fmt = detector.detect({"name": "my_tool", "input_schema": {"type": "object"}})
print(fmt)  # SourceFormat.anthropic
```

---

##### `confidence`

```python
def confidence(self, tool_def: dict[str, Any]) -> dict[SourceFormat, float]:
```

Return a confidence score in the range `[0.0, 1.0]` for each known format.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_def` | `dict[str, Any]` | The raw tool definition to score |

**Returns:** `dict[SourceFormat, float]` — mapping from each `SourceFormat` to a confidence score. `SourceFormat.raw` always has score `0.1` as a floor.

**Score meanings:**

| Score | Interpretation |
|-------|----------------|
| `1.0` | All definitive signals present |
| `0.7–0.9` | Strong signals present |
| `0.5–0.6` | Weak signals present (ambiguous) |
| `0.0–0.1` | No signals detected |

**Example:**

```python
scores = detector.confidence(tool_def)
for fmt, score in sorted(scores.items(), key=lambda x: -x[1]):
    print(f"{fmt.value:12s}: {score:.0%}")
```

---

### `Canonicalizer`

```python
class Canonicalizer:
```

Normalize tool definitions from any supported format to `CanonicalTool`. Instantiate once and reuse; the object is stateless with respect to tool data.

#### Constructor

```python
def __init__(self) -> None:
```

Instantiates the `FormatDetector` and all four format parsers. No configuration required.

#### Methods

---

##### `canonicalize`

```python
def canonicalize(
    self,
    tool_def: dict[str, Any],
    source_format: SourceFormat | None = None,
) -> CanonicalizationResult:
```

Normalize a tool definition dict into canonical IR.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_def` | `dict[str, Any]` | required | The raw tool definition to normalize |
| `source_format` | `SourceFormat \| None` | `None` | Force a specific source format. If `None`, auto-detection is used. |

**Returns:** `CanonicalizationResult` — always returned, never raises. Errors are surfaced as warnings.

**Behavior on parser failure:**

If the selected parser raises any exception, `canonicalize` catches it, appends a descriptive warning to `CanonicalizationResult.warnings`, and falls back to the raw heuristic extractor.

**Example:**

```python
from aumai_toolcanon.core import Canonicalizer
from aumai_toolcanon.models import SourceFormat

canon = Canonicalizer()

# Auto-detect format
result = canon.canonicalize(tool_def)

# Force a format
result = canon.canonicalize(tool_def, source_format=SourceFormat.anthropic)

# Always safe to access result.tool
print(result.tool.name)
print(result.source_format_detected)
print(result.warnings)
```

---

## Module `aumai_toolcanon.emitter`

Four pure functions for emitting a `CanonicalTool` to provider-specific formats.

```python
from aumai_toolcanon.emitter import (
    emit_openai,
    emit_anthropic,
    emit_mcp,
    emit_json_schema,
)
```

---

### `emit_openai`

```python
def emit_openai(tool: CanonicalTool) -> dict[str, Any]:
```

Emit a `CanonicalTool` as an OpenAI tool definition.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool` | `CanonicalTool` | The canonical tool to emit |

**Returns:** A `dict` conforming to the OpenAI tool calling format:

```json
{
  "type": "function",
  "function": {
    "name": "<name>",
    "description": "<description>",
    "parameters": { ... }
  }
}
```

If `tool.inputs` is empty, `parameters` defaults to `{"type": "object", "properties": {}}`. If `tool.inputs` exists but lacks a `"type"` key, `"type": "object"` is injected automatically.

---

### `emit_anthropic`

```python
def emit_anthropic(tool: CanonicalTool) -> dict[str, Any]:
```

Emit a `CanonicalTool` as an Anthropic tool definition.

**Returns:** A `dict` conforming to the Anthropic tool format:

```json
{
  "name": "<name>",
  "description": "<description>",
  "input_schema": { ... }
}
```

---

### `emit_mcp`

```python
def emit_mcp(tool: CanonicalTool) -> dict[str, Any]:
```

Emit a `CanonicalTool` as an MCP (Model Context Protocol) tool definition.

**Returns:** A `dict` conforming to the MCP tool format:

```json
{
  "name": "<name>",
  "description": "<description>",
  "inputSchema": { ... }
}
```

---

### `emit_json_schema`

```python
def emit_json_schema(tool: CanonicalTool) -> dict[str, Any]:
```

Emit a `CanonicalTool` as a standalone JSON Schema document (Draft 2019-09).

This is the richest emitter. In addition to the standard JSON Schema fields, it includes AumAI vendor extensions:

| Extension key | Source field | Content |
|---------------|-------------|---------|
| `x-capabilities` | `tool.capabilities` | `action`, `domain`, `side_effects`, `idempotent`, `cost_estimate` |
| `x-outputs` | `tool.outputs` | Output schema (only present if `tool.outputs` is non-empty) |
| `x-security` | `tool.security` | `required_permissions`, `data_classification`, `pii_handling` (only present if `tool.security` is not `None`) |

**Returns:** A `dict` with `$schema`, `title`, `description`, and the input schema merged at root level, plus the extension keys above.

**Example:**

```python
from aumai_toolcanon.emitter import emit_json_schema
from aumai_toolcanon.models import CanonicalTool, ToolCapability, ToolSecurity, SourceFormat

tool = CanonicalTool(
    name="delete_record",
    description="Delete a record permanently",
    capabilities=ToolCapability(action="delete", domain="database", side_effects=True),
    security=ToolSecurity(
        required_permissions=["records:delete"],
        data_classification="confidential",
        pii_handling="processes",
    ),
    inputs={"type": "object", "properties": {"id": {"type": "string"}}},
    source_format=SourceFormat.raw,
)

schema = emit_json_schema(tool)
print(schema["$schema"])              # "https://json-schema.org/draft/2019-09/schema"
print(schema["x-capabilities"])       # {"action": "delete", "domain": "database", ...}
print(schema["x-security"])           # {"required_permissions": [...], ...}
```

---

## Module `aumai_toolcanon.parsers`

Four format-specific parsers. You typically do not use these directly — `Canonicalizer` orchestrates them. They are documented here for completeness.

All parsers expose two methods:

```python
def parse(self, tool_def: dict[str, Any]) -> CanonicalTool: ...
def can_parse(self, tool_def: dict[str, Any]) -> bool: ...
```

### `OpenAIParser`

Handles both the wrapped format (`{"type":"function","function":{...}}`) and the legacy function call format (`{"name":..., "parameters":{...}}`).

### `AnthropicParser`

Handles `{"name":..., "description":..., "input_schema":{...}}`.

### `MCPParser`

Handles `{"name":..., "description":..., "inputSchema":{...}}`.

### `LangChainParser`

Handles `{"args_schema":..., ...}`, `{"schema":..., ...}`, and the loose `{"name":..., "properties":{...}}` shape.

---

## Package root exports

The following names are importable directly from `aumai_toolcanon`:

```python
from aumai_toolcanon import (
    CanonicalTool,
    CanonicalizationResult,
    SourceFormat,
    ToolCapability,
    ToolSecurity,
)
```

The core engine classes and emitters must be imported from their respective submodules:

```python
from aumai_toolcanon.core import Canonicalizer, FormatDetector
from aumai_toolcanon.emitter import emit_openai, emit_anthropic, emit_mcp, emit_json_schema
```
