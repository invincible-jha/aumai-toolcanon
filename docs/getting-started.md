# Getting Started with aumai-toolcanon

This guide takes you from a fresh installation to confidently normalizing and emitting tool definitions in any format. Estimated time: 20 minutes.

---

## Prerequisites

- Python 3.11 or later
- `pip` 23+ (ships with Python 3.11+)
- Basic familiarity with JSON and AI tool calling concepts

You do **not** need accounts with any AI provider to use aumai-toolcanon. It is a pure data transformation library that never makes network calls.

---

## Installation

### From PyPI (recommended)

```bash
pip install aumai-toolcanon
```

Verify the installation:

```bash
toolcanon --version
# aumai-toolcanon, version 0.1.0

python -c "import aumai_toolcanon; print(aumai_toolcanon.__version__)"
# 0.1.0
```

### From source

```bash
git clone https://github.com/aumai/aumai-toolcanon.git
cd aumai-toolcanon
pip install -e .
```

### Development mode (with test and lint dependencies)

```bash
git clone https://github.com/aumai/aumai-toolcanon.git
cd aumai-toolcanon
pip install -e ".[dev]"

# Run the test suite to confirm everything works
pytest
# Should show all tests passing
```

---

## Your First Canonicalization

### Step 1 — Create an input file

Save the following as `tool.json`. This is a standard OpenAI function calling definition:

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get the current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City name or coordinates"
        },
        "units": {
          "type": "string",
          "enum": ["celsius", "fahrenheit"],
          "description": "Temperature unit"
        }
      },
      "required": ["location"]
    }
  }
}
```

### Step 2 — Auto-detect the format

```bash
toolcanon detect --input tool.json
```

Output:

```
Detected format: openai
```

Add `--verbose` to see confidence scores:

```bash
toolcanon detect --input tool.json --verbose
```

Output:

```
Detected format: openai

Confidence scores:
  openai      : 100%
  langchain   :   0%
  anthropic   :   0%
  mcp         :   0%
  raw         :  10%
```

### Step 3 — Canonicalize it

```bash
toolcanon canonicalize --input tool.json
```

You will see the Canonical IR on stdout with inferred capability metadata:

```json
{
  "name": "get_weather",
  "version": "1.0.0",
  "description": "Get the current weather for a location",
  "capabilities": {
    "action": "get",
    "domain": "web",
    "side_effects": false,
    "idempotent": true,
    "cost_estimate": "unknown"
  },
  "inputs": { ... },
  "outputs": {},
  "security": null,
  "source_format": "openai",
  "original_definition": { ... }
}
```

### Step 4 — Save the canonical form and emit to another format

```bash
# Save canonical IR
toolcanon canonicalize --input tool.json --output canonical.json

# Emit to Anthropic format
toolcanon emit --input canonical.json --target anthropic
```

Anthropic output:

```json
{
  "name": "get_weather",
  "description": "Get the current weather for a location",
  "input_schema": {
    "type": "object",
    "properties": { ... },
    "required": ["location"]
  }
}
```

```bash
# Emit to MCP format
toolcanon emit --input canonical.json --target mcp
```

MCP output:

```json
{
  "name": "get_weather",
  "description": "Get the current weather for a location",
  "inputSchema": {
    "type": "object",
    "properties": { ... },
    "required": ["location"]
  }
}
```

### Step 5 — Try the Python API

```python
from aumai_toolcanon.core import Canonicalizer
from aumai_toolcanon.emitter import emit_anthropic, emit_mcp

import json

with open("tool.json") as f:
    tool_def = json.load(f)

canon = Canonicalizer()
result = canon.canonicalize(tool_def)

print(f"Detected: {result.source_format_detected.value}")
print(f"Tool name: {result.tool.name}")
print(f"Warnings: {result.warnings}")

# Emit to both formats
anthropic_tool = emit_anthropic(result.tool)
mcp_tool = emit_mcp(result.tool)
```

---

## Common Patterns

### Pattern 1 — Convert an entire tool library at once

If you have a directory of JSON tool definitions from different sources, canonicalize them all in a script:

```python
import json
from pathlib import Path
from aumai_toolcanon.core import Canonicalizer

canon = Canonicalizer()
tool_files = Path("./tools").glob("*.json")
canonical_tools = []

for tool_file in tool_files:
    tool_def = json.loads(tool_file.read_text())
    result = canon.canonicalize(tool_def)

    if result.warnings:
        print(f"[{tool_file.name}] warnings: {result.warnings}")

    canonical_tools.append(result.tool)

print(f"Canonicalized {len(canonical_tools)} tools")
```

### Pattern 2 — Build a multi-provider tool registry

Normalize all tools to canonical IR once, then emit to the right format per provider at dispatch time:

```python
from aumai_toolcanon.core import Canonicalizer
from aumai_toolcanon.emitter import emit_openai, emit_anthropic, emit_mcp
from aumai_toolcanon.models import CanonicalTool

# --- Normalize once at registration time ---
canon = Canonicalizer()
results = [canon.canonicalize(raw_def) for raw_def in raw_tool_definitions]
registry: list[CanonicalTool] = [r.tool for r in results]

# --- Emit at dispatch time based on the provider being called ---
def get_tools_for_provider(provider: str) -> list[dict]:
    emitters = {
        "openai": emit_openai,
        "anthropic": emit_anthropic,
        "mcp": emit_mcp,
    }
    emitter = emitters[provider]
    return [emitter(tool) for tool in registry]
```

### Pattern 3 — Validate tool quality before registration

Use the warnings in `CanonicalizationResult` to gate tool registration:

```python
from aumai_toolcanon.core import Canonicalizer

def register_tool(raw_def: dict) -> None:
    canon = Canonicalizer()
    result = canon.canonicalize(raw_def)

    if result.warnings:
        raise ValueError(
            f"Tool '{result.tool.name}' has quality issues: {result.warnings}"
        )

    # Proceed with registration
    save_to_registry(result.tool)
```

### Pattern 4 — Attach security metadata after canonicalization

```python
from aumai_toolcanon.core import Canonicalizer
from aumai_toolcanon.models import ToolSecurity

canon = Canonicalizer()
result = canon.canonicalize(raw_def)

# Overlay security policy based on your own classification logic
tool = result.tool.model_copy(
    update={
        "security": ToolSecurity(
            required_permissions=["tools:invoke"],
            data_classification="internal",
            pii_handling="none",
        )
    }
)
```

### Pattern 5 — Programmatically detect ambiguous tools

If a tool definition could match multiple formats, check confidence scores before committing:

```python
from aumai_toolcanon.core import FormatDetector
from aumai_toolcanon.models import SourceFormat

detector = FormatDetector()
scores = detector.confidence(ambiguous_tool_def)

# Find the top two candidates
sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
top_format, top_score = sorted_scores[0]
second_format, second_score = sorted_scores[1]

if top_score - second_score < 0.3:
    print(f"Ambiguous: {top_format.value} ({top_score:.0%}) vs "
          f"{second_format.value} ({second_score:.0%}). Review manually.")
else:
    print(f"Confident: {top_format.value} ({top_score:.0%})")
```

---

## Troubleshooting FAQ

**Q: `toolcanon: command not found` after `pip install`**

Your pip script directory is not on `PATH`. Try:

```bash
python -m aumai_toolcanon.cli --version
```

Or find the scripts directory:

```bash
python -c "import site; print(site.getsitepackages())"
```

And add the `bin` or `Scripts` subdirectory to your `PATH`.

---

**Q: Warnings appear but I still get a canonical tool — is that normal?**

Yes. Warnings are non-fatal quality advisories. The most common ones are:

- `"Tool has no name"` — the input had no detectable name field
- `"Tool has no description"` — the input had no description
- `"Could not detect source format; using raw passthrough"` — the input does not match any known format

In all cases, `CanonicalizationResult.tool` is always populated with a best-effort canonical tool. You decide whether to accept or reject it based on the warnings.

---

**Q: How do I handle a format that is not OpenAI, Anthropic, MCP, or LangChain?**

Pass `source_format=SourceFormat.raw` explicitly. The raw canonicalizer will attempt to extract `name`, `description`, and the first schema-like key it finds (`parameters`, `input_schema`, `inputSchema`, or `schema`).

Alternatively, construct a `CanonicalTool` directly with all fields you need.

---

**Q: The capability inference is wrong for my tool. How do I fix it?**

Construct `ToolCapability` explicitly and pass it during canonicalization:

```python
from aumai_toolcanon.models import CanonicalTool, ToolCapability, SourceFormat

tool = CanonicalTool(
    name="send_email",
    description="Send an email message",
    capabilities=ToolCapability(
        action="send",
        domain="email",
        side_effects=True,
        idempotent=False,
        cost_estimate="low",
    ),
    inputs=my_schema,
    source_format=SourceFormat.openai,
)
```

---

**Q: `emit_json_schema` output has `x-capabilities` and `x-security`. Are these standard?**

They follow the JSON Schema convention for vendor extensions (keys prefixed with `x-`). They are not part of any official JSON Schema draft but are valid in all compliant validators, which ignore unknown extension properties. Tools like `aumai-toolregistry` are aware of these extensions and index them for search and policy enforcement.

---

**Q: Can I round-trip a tool definition through canonical IR without loss?**

Almost. The canonical format preserves the full original definition in `original_definition`, so you can always access the raw input. However, emitters reconstruct the output format from the canonical fields, not from `original_definition` — so comments, extra fields, and non-standard extensions in the original will not appear in the emitted output. This is intentional: the emitters produce clean, spec-compliant output.
