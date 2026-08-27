"""
Unit and integration tests for llm_model module in OCRATION.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

import llm_model


class TestLLMProviders:
    """Test LLM Provider abstractions and configuration."""

    def test_groq_provider_initialization(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_valid_key_12345")
        provider = llm_model.GroqProvider()
        assert provider.is_available() is True
        assert provider.model == "llama-3.3-70b-versatile"

    def test_groq_provider_missing_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        provider = llm_model.GroqProvider()
        assert provider.is_available() is False

    @patch("requests.post")
    def test_groq_provider_successful_call(self, mock_post, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_valid_key_12345")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Sample structured translation"}}]
        }
        mock_post.return_value = mock_response

        provider = llm_model.GroqProvider()
        output = provider.call("System prompt", "User document text")
        assert output == "Sample structured translation"


class TestJSONParsingAndEntityExtraction:
    """Test JSON extraction and fallback parsing."""

    def test_parse_json_safely_valid(self):
        raw = 'Some preliminary text {"name": "Alice", "email": "alice@test.com"} trailing text'
        parsed = llm_model._parse_json_safely(raw)
        assert parsed.get("name") == "Alice"
        assert parsed.get("email") == "alice@test.com"

    def test_parse_json_safely_invalid(self):
        raw = "Not a json text at all"
        assert llm_model._parse_json_safely(raw) == {}

    def test_extract_entities_json_empty_input(self):
        assert llm_model.extract_entities_json("") == {}
        assert llm_model.extract_entities_json(None) == {}

    @patch("llm_model._current_provider.call")
    @patch("llm_model._current_provider.is_available")
    def test_extract_entities_json_mocked(self, mock_avail, mock_call):
        mock_avail.return_value = True
        mock_call.return_value = '{"name": "Jane Doe", "email": "jane@corp.com", "phone": "123-456-7890", "address": "Cairo, Egypt"}'

        result = llm_model.extract_entities_json("Sample contact card text")
        assert result["name"] == "Jane Doe"
        assert result["email"] == "jane@corp.com"
        assert result["phone"] == "123-456-7890"
        assert result["address"] == "Cairo, Egypt"
