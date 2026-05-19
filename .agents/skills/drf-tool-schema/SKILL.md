---
name: drf-tool-schema
description: "Generate LLM function-calling tool schemas from Django REST Framework serializers using drf-tool-schema. Use when: building AI agents with Django/DRF; converting DRF serializers to OpenAI/Anthropic/OpenRouter tool schemas; wiring Django models to LLM tool-calling; creating function schemas for GPT, Claude, Groq, Mistral; keeping tool schemas in sync with DRF serializers automatically."
argument-hint: "serializer class or use-case to generate tool schema for"
---

# drf-tool-schema

Generates OpenAI-compatible function-calling tool schemas by introspecting Django REST Framework serializers. Eliminates hand-written JSON schemas — change a serializer field and the schema updates automatically.

Compatible with: **OpenAI**, **Anthropic Claude**, **OpenRouter**, **Groq**, **Mistral**, **LiteLLM**, and any OpenAI-compatible provider.

## Installation

```bash
pip install drf-tool-schema
```

## Core function

```python
from drf_tool_schema import schema_from_serializer
```

### Signature

```python
schema_from_serializer(
    name: str,
    description: str,
    serializer: Serializer,
    required_override: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict
```

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Tool name in snake_case (e.g. `"create_customer"`) |
| `description` | `str` | Plain-language description sent to the LLM |
| `serializer` | `Serializer` | **Instantiated** DRF serializer (call it: `MySerializer()`) |
| `required_override` | `list[str] \| None` | Explicit required fields. If `None`, uses each field's `required` flag |
| `exclude` | `list[str] \| None` | Field names to exclude in addition to read-only fields |

> Read-only fields (`read_only=True`) are **always** excluded automatically.

## Basic usage

```python
from drf_tool_schema import schema_from_serializer
from myapp.serializers import CustomerSerializer

tool = schema_from_serializer(
    name="create_customer",
    description="Creates a new customer in the system. Returns the created customer ID.",
    serializer=CustomerSerializer(),
)
```

### Output format

```json
{
  "type": "function",
  "function": {
    "name": "create_customer",
    "description": "Creates a new customer in the system.",
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

## Passing schemas to LLM providers

```python
TOOLS = [
    schema_from_serializer(name="create_customer", description="...", serializer=CustomerSerializer()),
    schema_from_serializer(name="update_invoice",  description="...", serializer=InvoiceSerializer()),
]

# OpenAI
client.chat.completions.create(model="gpt-4o", messages=[...], tools=TOOLS)

# Anthropic Claude
client.messages.create(model="claude-opus-4-5", messages=[...], tools=TOOLS)

# OpenRouter / Groq / Mistral / LiteLLM
client.chat.completions.create(model="...", messages=[...], tools=TOOLS)
```

## Field type mapping

| DRF field class | JSON Schema type | Notes |
|---|---|---|
| `CharField`, `EmailField`, `URLField`, `UUIDField`, `DateField`, `DateTimeField` | `string` | |
| `IntegerField` | `integer` | Includes `minimum` / `maximum` when set |
| `DecimalField`, `FloatField` | `number` | |
| `BooleanField` | `boolean` | |
| `ChoiceField` | `string` + `enum` | Enum values from `choices` |
| `ListField` | `array` | `items` schema derived from `child` field |
| Nested `Serializer` | `object` | Inlined with its own `properties` and `required` |

Field descriptions come from `help_text` first, then `label`. Fields with `default` values include a `"default"` key.

## Common patterns

### Override required fields

```python
# Only legal_name and tax_id are required, regardless of serializer flags
tool = schema_from_serializer(
    name="create_customer",
    description="...",
    serializer=CustomerSerializer(),
    required_override=["legal_name", "tax_id"],
)
```

### Exclude sensitive or irrelevant fields

```python
tool = schema_from_serializer(
    name="create_customer",
    description="...",
    serializer=CustomerSerializer(),
    exclude=["internal_notes", "created_by"],
)
```

### Nested serializers (inline objects)

```python
class AddressSerializer(serializers.Serializer):
    street = serializers.CharField(help_text="Street name and number.")
    city   = serializers.CharField(help_text="City.")
    zip    = serializers.CharField(help_text="Postal code.")

class OrderSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(help_text="Product ID.")
    quantity   = serializers.IntegerField(min_value=1, help_text="Units to order.")
    address    = AddressSerializer(help_text="Delivery address.")

tool = schema_from_serializer(
    name="place_order",
    description="Places a new order.",
    serializer=OrderSerializer(),
)
# address → { "type": "object", "properties": { "street": ..., "city": ..., "zip": ... } }
```

### Building a full tool list for an agent

```python
# tools.py
from drf_tool_schema import schema_from_serializer
from partners.serializers import PartnerWriteSerializer
from invoices.serializers import InvoiceCreateSerializer

AGENT_TOOLS = [
    schema_from_serializer(
        name="create_partner",
        description="Creates a supplier or customer partner. Returns the new partner ID.",
        serializer=PartnerWriteSerializer(),
        required_override=["legal_name", "tax_id"],
    ),
    schema_from_serializer(
        name="create_invoice",
        description="Creates a draft invoice for an existing partner.",
        serializer=InvoiceCreateSerializer(),
        exclude=["pdf_url", "created_at"],
    ),
]
```

## Best practices

- **Always instantiate** the serializer: pass `MySerializer()`, not `MySerializer`.
- Add `help_text` to every serializer field — it becomes the property description the LLM reads.
- Use `required_override` when the LLM only needs a subset of what the serializer validates.
- Use `exclude` to hide fields the LLM should never touch (audit fields, internal flags).
- Keep tool `name` in **snake_case** — some providers reject camelCase or spaces.
- Keep `description` focused on what the tool does and what it returns — this is the LLM's primary signal for tool selection.

## Development

```bash
pip install -e ".[dev]"
pytest
```
