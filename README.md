# drf-tool-schema

Generate function-calling tool schemas from Django REST Framework serializers. Compatible with any LLM provider that follows the OpenAI tool calling standard — including OpenAI, Anthropic Claude, OpenRouter, Groq, Mistral, and LiteLLM.

Instead of writing tool schemas by hand and keeping them in sync with your serializers manually, `drf-tool-schema` introspects the serializer and builds the schema automatically. Change a field in your serializer and the tool schema updates with it.

## Installation

```bash
pip install drf-tool-schema
```

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

This produces:

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

Pass the schema directly to your LLM client:

```python
# OpenAI
client.chat.completions.create(model="gpt-4o", messages=[...], tools=SCHEMAS)

# Anthropic Claude
client.messages.create(model="claude-sonnet-4-20250514", messages=[...], tools=SCHEMAS)

# OpenRouter / Groq / Mistral / any OpenAI-compatible provider
client.chat.completions.create(model="...", messages=[...], tools=SCHEMAS)
```

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Tool name in snake_case |
| `description` | `str` | Description sent to the LLM |
| `serializer` | `Serializer` | Instantiated DRF serializer |
| `required_override` | `list[str] \| None` | Override required fields. If `None`, uses serializer's `required` flags |
| `exclude` | `list[str] \| None` | Field names to exclude (read-only fields are always excluded) |

## Field type mapping

| DRF field | JSON Schema type |
|---|---|
| `CharField`, `EmailField`, `URLField`, `DateField`, `DateTimeField`, `UUIDField` | `string` |
| `IntegerField` | `integer` (with `minimum` / `maximum` if set) |
| `DecimalField`, `FloatField` | `number` |
| `BooleanField` | `boolean` |
| `ChoiceField` | `string` + `enum` |
| `ListField` | `array` |
| Nested `Serializer` | `object` (inlined) |

Fields with `read_only=True` are always excluded.
Field descriptions come from `help_text`, falling back to `label`.

## Development

```bash
pip install -e ".[dev]"
pytest
# or without pytest:
python tests/test_builder.py
```

## License

MIT
