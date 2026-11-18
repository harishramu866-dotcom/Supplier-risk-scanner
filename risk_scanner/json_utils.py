"""Shared helper for parsing JSON out of a model's text response."""

import json


def parse_json_object(text: str) -> dict:
    """Parse the first JSON object in `text`, ignoring code fences and any prose around it."""
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in model output: {text!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj
