"""
Unit and integration tests for OCRation_App.
Tests OCR text extraction, LLM translation, and end-to-end integration pipeline.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

import image_ocr
import llm_model
from image_ocr import extract_text
from llm_model import translate


class TestOCRModule:
    """Test suite for OCR extraction module."""

    def test_extract_text_returns_string(self, sample_image):
        """Verify that extract_text returns a string when given a valid image file."""
        with patch.object(image_ocr, "extract_text_from_path", return_value={"text": "Hello World", "tables": []}):
            result = extract_text(sample_image)
            assert isinstance(result, str)

    def test_nonexistent_file_raises(self):
        """Verify that extract_text raises an error when the image file does not exist."""
        with pytest.raises((FileNotFoundError, Exception)):
            extract_text("no_such_file.jpg")

    def test_extract_text_not_none(self, sample_image):
        """Verify that extract_text result is never None for valid input."""
        with patch.object(image_ocr, "extract_text_from_path", return_value={"text": "Hello World", "tables": []}):
            result = extract_text(sample_image)
            assert result is not None
            assert isinstance(result, str)


class TestLLMModel:
    """Test suite for LLM translation module."""

    def test_translate_returns_string(self, mock_groq_response):
        """Verify that translate returns a string response from LLM."""
        # Mock requests.post or Groq API provider response
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_groq_response
            mock_post.return_value = mock_resp
            
            # Ensure provider uses Groq response
            with patch.object(llm_model, "is_llm_available", return_value=True):
                with patch.object(llm_model._current_provider, "call", return_value="مرحبا بالعالم"):
                    result = translate("Hello World", target_lang="ar")
                    assert isinstance(result, str)
                    assert len(result) > 0

    def test_empty_input_returns_empty(self):
        """Verify that passing an empty string to translate returns an empty string without making API calls."""
        result = translate("", target_lang="ar")
        assert result == ""


class TestIntegration:
    """Integration test suite for OCRation pipeline."""

    def test_full_pipeline(self, sample_image, mock_groq_response):
        """Verify complete pipeline: Image -> OCR text extraction -> LLM translation."""
        with patch.object(image_ocr, "extract_text_from_path", return_value={"text": "Hello World", "tables": []}):
            ocr_text = extract_text(sample_image)
            assert isinstance(ocr_text, str)
            assert len(ocr_text) > 0

            with patch.object(llm_model, "is_llm_available", return_value=True):
                with patch.object(llm_model._current_provider, "call", return_value="مرحبا بالعالم"):
                    final_output = translate(ocr_text, target_lang="ar")
                    assert isinstance(final_output, str)
                    assert len(final_output) > 0
                    assert final_output == "مرحبا بالعالم"
