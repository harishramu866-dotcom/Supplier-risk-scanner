"""Schema validation for the SupplierRiskReport JSON shape."""

import json
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "risk_report.schema.json"


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_report(report: dict, schema: dict | None = None) -> None:
    """Raises jsonschema.ValidationError if `report` doesn't match the schema."""
    jsonschema.validate(instance=report, schema=schema or load_schema())


def is_valid_report(report: dict, schema: dict | None = None) -> bool:
    try:
        validate_report(report, schema)
        return True
    except jsonschema.ValidationError:
        return False


def validate_category_result(category_result: dict, schema: dict | None = None) -> None:
    """Raises jsonschema.ValidationError if a single category's {status, findings} doesn't match."""
    schema = schema or load_schema()
    jsonschema.validate(instance=category_result, schema=schema["definitions"]["category"])


def is_valid_category_result(category_result: dict, schema: dict | None = None) -> bool:
    try:
        validate_category_result(category_result, schema)
        return True
    except jsonschema.ValidationError:
        return False
