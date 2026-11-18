import json
from types import SimpleNamespace

import pytest


class FakeClient:
    """Stands in for anthropic.Anthropic so tests never touch the live API."""

    def __init__(self, response):
        self.text = response if isinstance(response, str) else json.dumps(response)
        self.prompts = []
        self.messages = self

    def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


@pytest.fixture
def fake_client():
    return FakeClient
