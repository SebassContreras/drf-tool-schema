# drf-tool-schema

[![Tests](https://github.com/SebassContreras/drf-tool-schema/actions/workflows/test.yml/badge.svg)](https://github.com/SebassContreras/drf-tool-schema/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/drf-tool-schema.svg)](https://pypi.org/project/drf-tool-schema/)
[![Python versions](https://img.shields.io/pypi/pyversions/drf-tool-schema.svg)](https://pypi.org/project/drf-tool-schema/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Make an existing Django REST Framework API callable by an LLM.**

You already have the API. The serializers already declare every field type, required flag, choice, bound
and human-readable description that an LLM needs in order to call it correctly. `drf-tool-schema` reads
that declaration and emits the function-calling schema, so you can hand an agent your real endpoints
instead of building a parallel interface for it.

Works with any provider that follows the OpenAI tool-calling format — OpenAI, Anthropic Claude,
OpenRouter, Groq, Mistral, LiteLLM.

```python
schema_from_serializer(
    name="create_customer",
    description="Creates a new customer. Returns the created customer ID.",
    serializer=CustomerSerializer(),
)
```

---

## Why

An LLM can only call what you describe to it. To let an agent create a customer, register an invoice or
update an order against your Django backend, every one of those actions needs a schema declaring its
parameters — and that schema has to match what your API actually accepts, or the call fails.

Written by hand, it restates what the serializer already says:

```python
# serializers.py — the source of truth
class CustomerSerializer(serializers.Serializer):
    legal_name = serializers.CharField(help_text="Official registered company name.")
    tax_id     = serializers.CharField(help_text="NIF / CIF / VAT number.")
    country    = serializers.ChoiceField(choices=COUNTRIES, default="ES")

# tools.py — the same thing again, by hand, in JSON
{"name": "create_customer", "parameters": {"type": "object", "properties": {
    "legal_name": {"type": "string", "description": "Official registered company name."},
    ...
}}}
```

Two definitions of one contract, and the hand-written one goes stale first. Add a field to the serializer
and the agent keeps sending the old shape — no error, no test failure, just a tool call your API rejects
at runtime.

Deriving the schema from the serializer removes the second definition: the API describes itself, and the
agent gets that description. Your endpoints stay the single source of truth for what a valid write looks
like, whether the caller is a browser or a model.

## Installation

```bash
pip install drf-tool-schema
```

Requires Python ≥ 3.11 and `djangorestframework` ≥ 3.14. No other dependencies — it does not import or
require any LLM SDK.

## Usage

```python
from drf_tool_schema import schema_from_serializer
from partners.serializers import PartnerWriteSerializer

SCHEMAS = [
    schema_from_serializer(
        name="create_customer",
        description="Creates a new customer in the system. Returns the created customer ID.",
        serializer=PartnerWriteSerializer(),
        required_override=["legal_name", "tax_id"],
    ),
]
```

Produces:

```json
{
  "type": "function",
  "function": {
    "name": "create_customer",
    "description": "Creates a new customer in the system. Returns the created customer ID.",
    "parameters": {
      "type": "object",
      "properties": {
        "legal_name": { "type": "string", "description": "Official registered company name." },
        "tax_id":     { "type": "string", "description": "NIF / CIF / VAT number." },
        "country":    { "type": "string", "description": "ISO 3166-1 alpha-2 country code.", "default": "ES" }
      },
      "required": ["legal_name", "tax_id"]
    }
  }
}
```

Pass it straight to your client:

```python
# OpenAI
client.chat.completions.create(model="gpt-4o", messages=[...], tools=SCHEMAS)

# Anthropic Claude
client.messages.create(model="claude-sonnet-4-5", messages=[...], tools=SCHEMAS)

# OpenRouter / Groq / Mistral / LiteLLM / any OpenAI-compatible provider
client.chat.completions.create(model="...", messages=[...], tools=SCHEMAS)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Tool name in snake_case |
| `description` | `str` | Description sent to the LLM — its primary signal for tool selection |
| `serializer` | `Serializer` | **Instantiated** serializer: `MySerializer()`, not `MySerializer` |
| `required_override` | `list[str] \| None` | Explicit required fields. If `None`, uses each field's `required` flag |
| `exclude` | `list[str] \| None` | Fields to omit, in addition to read-only fields |

### Field type mapping

| DRF field | JSON Schema | Notes |
|---|---|---|
| `CharField`, `EmailField`, `URLField`, `UUIDField`, `DateField`, `DateTimeField` | `string` | Default for unrecognised fields |
| `IntegerField` | `integer` | Emits `minimum` / `maximum` when `min_value` / `max_value` are set |
| `DecimalField`, `FloatField` | `number` | |
| `BooleanField` | `boolean` | |
| `ChoiceField` | `string` + `enum` | Enum values from `choices` |
| `ListField` | `array` | `items` derived recursively from `child` |
| Nested `Serializer` | `object` | Inlined, with its own `properties` and `required` |

Descriptions come from `help_text`, falling back to `label`, omitted if neither is set. Fields with a
`default` carry it into the schema. **Read-only fields are always excluded** — the LLM should never be
asked to supply a server-generated value.

## Common patterns

**Restrict what the LLM must provide.** A serializer may require ten fields for a valid write while the
agent only needs to supply two:

```python
schema_from_serializer(..., required_override=["legal_name", "tax_id"])
```

**Hide fields the LLM should never touch** — audit columns, internal flags, ownership:

```python
schema_from_serializer(..., exclude=["internal_notes", "created_by"])
```

**Build the agent's whole toolbox in one place:**

```python
AGENT_TOOLS = [
    schema_from_serializer(name="create_partner", description="...", serializer=PartnerWriteSerializer()),
    schema_from_serializer(name="create_invoice", description="...", serializer=InvoiceCreateSerializer()),
]
```

## Scope

**What this does:** turns one instantiated DRF serializer into one OpenAI-format tool schema. That is the
whole surface area — a single pure function, no Django app to install, no settings, no migrations, no
runtime hooks.

**What it deliberately does not do:**

| Not included | Why |
|---|---|
| Executing tool calls | Dispatch, auth and error handling belong to your app, not a schema builder |
| Reading `ViewSet`s, models or URLconf | The serializer is the write contract; inferring from views guesses at intent |
| Provider-specific schema dialects | Every major provider accepts the OpenAI format; emitting one shape keeps the output portable |
| Validating the LLM's response | That's what the serializer itself is for — feed the tool arguments back through it |
| `$ref` / `$defs` for repeated nested objects | Nested serializers are inlined; deeply recursive schemas will repeat themselves |

**Known limitations.** `SerializerMethodField` and other custom fields fall through to `string`, since
their output type isn't introspectable. `PrimaryKeyRelatedField` is not special-cased and maps to
`string`. There is no cycle detection on self-referencing nested serializers.

## Status

**Alpha (0.1.x).** The public API is one function and is unlikely to change shape, but treat minor
versions as breaking until 1.0.

Covered by 19 unit tests over the field mapping, required/exclude handling, nested serializers and
description fallbacks, run against Python 3.11 and 3.12 on every push and pull request. Released to PyPI
from a tagged commit via GitHub Actions using
[trusted publishing](https://docs.pypi.org/trusted-publishers/) — no API tokens stored in the repo.

## Using it with Claude Code

The repo ships an agent skill at `.agents/skills/drf-tool-schema/SKILL.md`. Copy that directory into a
project and [Claude Code](https://claude.com/claude-code) picks up the full API surface, the field
mapping table and the usage patterns automatically, so it wires serializers to tool schemas without
being re-taught each session.

## Development

```bash
git clone https://github.com/SebassContreras/drf-tool-schema.git
cd drf-tool-schema
pip install -e ".[dev]"
pytest
```

Tests configure Django settings inline, so no project scaffolding is needed.

## Contributing

Issues and pull requests are welcome at
[github.com/SebassContreras/drf-tool-schema](https://github.com/SebassContreras/drf-tool-schema/issues).
If you're reporting a field type that maps badly, a failing test case is the most useful thing you can
attach.

## License

MIT — see [LICENSE](LICENSE).
