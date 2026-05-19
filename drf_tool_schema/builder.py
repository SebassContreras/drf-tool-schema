from __future__ import annotations

from typing import Any

from rest_framework import serializers


def schema_from_serializer(
    name: str,
    description: str,
    serializer: serializers.Serializer,
    required_override: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate an OpenAI / OpenRouter tool call schema
    from a DRF serializer.

    Args:
        name:              Tool name (snake_case, e.g. "crear_cliente").
        description:       Human-readable description sent to the LLM.
        serializer:        Instantiated DRF serializer to introspect.
        required_override: Explicit list of required field names.
                   When provided,
                           the serializer's own `required` flags are ignored.
        exclude:           Field names to exclude from the schema (in addition
                           to read-only fields, which are always excluded).

    Returns:
        A dict in the OpenAI function-calling tool format::

            {
                "type": "function",
                "function": {
                    "name": ...,
                    "description": ...,
                    "parameters": {
                        "type": "object",
                        "properties": {...},
                        "required": [...],
                    },
                },
            }
    """
    excluded: set[str] = set(exclude or [])
    properties: dict[str, Any] = {}
    auto_required: list[str] = []

    for field_name, field in serializer.fields.items():
        if field.read_only or field_name in excluded:
            continue

        prop = _field_to_property(field)
        properties[field_name] = prop

        if field.required:
            auto_required.append(field_name)

    required = (
        required_override
        if required_override is not None
        else auto_required
    )

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


# Field type mapping

def _field_to_property(field: serializers.Field) -> dict[str, Any]:
    prop: dict[str, Any] = {}

    description = _field_description(field)
    if description:
        prop["description"] = description

    _apply_type_mapping(field, prop)

    # Default value (only for non-empty defaults)
    if field.default is not serializers.empty:
        prop["default"] = field.default

    return prop


def _field_description(field: serializers.Field) -> str:
    if field.help_text:
        return str(field.help_text).strip()
    if field.label:
        return str(field.label).strip()
    return ""


def _apply_type_mapping(
    field: serializers.Field,
    prop: dict[str, Any],
) -> None:
    for field_type, mapper in _FIELD_MAPPERS:
        if isinstance(field, field_type):
            mapper(field, prop)
            return

    # CharField, EmailField, URLField, DateField,
    # DateTimeField, UUIDField, etc.
    prop["type"] = "string"


def _map_choice_field(
    field: serializers.ChoiceField,
    prop: dict[str, Any],
) -> None:
    prop["type"] = "string"
    prop["enum"] = list(field.choices.keys())


def _map_boolean_field(
    field: serializers.BooleanField,
    prop: dict[str, Any],
) -> None:
    prop["type"] = "boolean"


def _map_integer_field(
    field: serializers.IntegerField,
    prop: dict[str, Any],
) -> None:
    prop["type"] = "integer"
    if field.min_value is not None:
        prop["minimum"] = field.min_value
    if field.max_value is not None:
        prop["maximum"] = field.max_value


def _map_number_field(
    field: serializers.Field,
    prop: dict[str, Any],
) -> None:
    prop["type"] = "number"


def _map_list_field(
    field: serializers.ListField,
    prop: dict[str, Any],
) -> None:
    prop["type"] = "array"
    if field.child:
        prop["items"] = _field_to_property(field.child)


def _map_nested_serializer(
    field: serializers.Serializer,
    prop: dict[str, Any],
) -> None:
    # Nested serializer -> inline object.
    nested_props: dict[str, Any] = {}
    nested_required: list[str] = []
    for child_name, child_field in field.fields.items():
        if child_field.read_only:
            continue
        nested_props[child_name] = _field_to_property(child_field)
        if child_field.required:
            nested_required.append(child_name)

    prop["type"] = "object"
    prop["properties"] = nested_props
    if nested_required:
        prop["required"] = nested_required


_FIELD_MAPPERS: list[tuple[type[Any] | tuple[type[Any], ...], Any]] = [
    (serializers.ChoiceField, _map_choice_field),
    (serializers.BooleanField, _map_boolean_field),
    (serializers.IntegerField, _map_integer_field),
    ((serializers.DecimalField, serializers.FloatField), _map_number_field),
    (serializers.ListField, _map_list_field),
    (serializers.Serializer, _map_nested_serializer),
]
