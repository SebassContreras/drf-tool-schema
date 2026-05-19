from __future__ import annotations

from typing import Any, cast

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["rest_framework"],
        DATABASES={},
    )
    django.setup()

from rest_framework import serializers

from drf_tool_schema import schema_from_serializer


# Fixtures

class AddressSerializer(serializers.Serializer):
    street_name = serializers.CharField(help_text="Street name.")
    street_number = serializers.CharField(help_text="Street number.")
    city = serializers.CharField(help_text="City.")
    postal_code = serializers.CharField(help_text="Postal code.")


class PartnerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    legal_name = serializers.CharField(
        help_text="Official registered company name."
    )
    tax_id = serializers.CharField(help_text="NIF / CIF / VAT number.")
    country = serializers.CharField(
        help_text="ISO 3166-1 alpha-2 country code.",
        default="ES",
        required=False,
    )
    commercial_name = serializers.CharField(
        required=False,
        help_text="Trading name.",
    )
    is_active = serializers.BooleanField(default=True, required=False)
    employee_count = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=100_000,
        help_text="Number of employees.",
    )
    revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        help_text="Annual revenue.",
    )
    category = serializers.ChoiceField(
        choices=["customer", "carrier", "both"],
        required=False,
        help_text="Partner category.",
    )
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Freeform tags.",
    )
    address = AddressSerializer(required=False, help_text="Primary address.")


class LabelOnlySerializer(serializers.Serializer):
    nickname = serializers.CharField(label="Nickname")


class NoMetadataSerializer(serializers.Serializer):
    plain_text = serializers.CharField(label="", help_text="")


class FloatSerializer(serializers.Serializer):
    score = serializers.FloatField(required=False)


class NestedChildSerializer(serializers.Serializer):
    nested_required = serializers.CharField()
    nested_read_only = serializers.IntegerField(read_only=True)


class NestedParentSerializer(serializers.Serializer):
    child = NestedChildSerializer(required=False)


def _as_serializer(serializer: Any) -> serializers.Serializer:
    return cast(serializers.Serializer, serializer)


# Tests

def test_top_level_structure():
    schema = schema_from_serializer(
        name="crear_cliente",
        description="Creates a customer.",
        serializer=_as_serializer(PartnerSerializer()),
    )
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "crear_cliente"
    assert fn["description"] == "Creates a customer."
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "properties" in params
    assert "required" in params


def test_read_only_excluded():
    schema = schema_from_serializer(
        name="crear_cliente",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )
    assert "id" not in schema["function"]["parameters"]["properties"]


def test_required_fields_auto():
    schema = schema_from_serializer(
        name="crear_cliente",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )
    required = schema["function"]["parameters"]["required"]
    assert "legal_name" in required
    assert "tax_id" in required
    assert "country" not in required
    assert "commercial_name" not in required


def test_required_override():
    schema = schema_from_serializer(
        name="crear_cliente",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
        required_override=["legal_name"],
    )
    assert schema["function"]["parameters"]["required"] == ["legal_name"]


def test_exclude():
    schema = schema_from_serializer(
        name="crear_cliente",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
        exclude=["revenue", "tags"],
    )
    props = schema["function"]["parameters"]["properties"]
    assert "revenue" not in props
    assert "tags" not in props
    assert "legal_name" in props


def test_map_choice_field_type_and_enum():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["category"]["type"] == "string"
    assert props["category"]["enum"] == ["customer", "carrier", "both"]


def test_map_boolean_field_type():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["is_active"]["type"] == "boolean"


def test_map_integer_field_constraints():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["employee_count"]["type"] == "integer"
    assert props["employee_count"]["minimum"] == 0
    assert props["employee_count"]["maximum"] == 100_000


def test_map_number_field_type_for_decimal():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["revenue"]["type"] == "number"


def test_map_number_field_type_for_float():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(FloatSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["score"]["type"] == "number"


def test_map_list_field_type_and_items():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["tags"]["type"] == "array"
    assert props["tags"]["items"]["type"] == "string"


def test_map_fallback_string_field_type():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["legal_name"]["type"] == "string"


def test_default_value():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert props["country"]["default"] == "ES"
    assert props["is_active"]["default"] is True


def test_nested_serializer():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    address = props["address"]
    assert address["type"] == "object"
    assert "street_name" in address["properties"]
    assert address["properties"]["city"]["type"] == "string"


def test_map_nested_serializer_skips_read_only_and_sets_required():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(NestedParentSerializer()),
    )["function"]["parameters"]["properties"]
    child = props["child"]
    assert child["type"] == "object"
    assert "nested_required" in child["properties"]
    assert "nested_read_only" not in child["properties"]
    assert child["required"] == ["nested_required"]


def test_help_text_as_description():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(PartnerSerializer()),
    )["function"]["parameters"]["properties"]
    assert (
        props["legal_name"]["description"]
        == "Official registered company name."
    )


def test_description_falls_back_to_label():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(LabelOnlySerializer()),
    )["function"]["parameters"]["properties"]
    assert props["nickname"]["description"] == "Nickname"


def test_description_omitted_when_empty():
    props = schema_from_serializer(
        name="x",
        description=".",
        serializer=_as_serializer(NoMetadataSerializer()),
    )["function"]["parameters"]["properties"]
    assert "description" not in props["plain_text"]


def test_empty_serializer():
    class EmptySerializer(serializers.Serializer):
        pass

    schema = schema_from_serializer(
        name="noop",
        description=".",
        serializer=_as_serializer(EmptySerializer()),
    )
    assert schema["function"]["parameters"]["properties"] == {}
    assert schema["function"]["parameters"]["required"] == []


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ✗ {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
