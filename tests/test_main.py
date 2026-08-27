"""
Main integration test suite for OCRATION application.
Validates complete workflows across Image OCR, LLM, and Logging subsystems.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

import image_ocr
import llm_model
import logging_config
from exceptions import OCRationError


class TestEndToEndPipeline:
    """End-to-End integration tests for OCR and Translation."""

    def test_logging_initialization(self, tmp_path):
        """Verify rotating logger initializes without errors."""
        test_log_dir = str(tmp_path / "logs")
        logger = logging_config.setup_logging(log_dir=test_log_dir, log_file_name="test.log")
        assert logger is not None
        assert os.path.exists(test_log_dir)

    @patch("image_ocr._session.post")
    @patch("llm_model._current_provider.call")
    @patch("llm_model._current_provider.is_available")
    def test_full_ocr_and_entity_extraction_flow(
        self,
        mock_llm_avail,
        mock_llm_call,
        mock_ocr_post,
        sample_image_path,
        mock_ocr_success_response
    ):
        """Simulate end-to-end OCR processing followed by LLM entity extraction."""
        # 1. Mock OCR Space response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_ocr_success_response
        mock_ocr_post.return_value = mock_resp

        # 2. Mock LLM Response
        mock_llm_avail.return_value = True
        mock_llm_call.return_value = '{"name": "Client Corp", "email": "contact@client.com", "phone": "555-0199", "address": "Tech Park"}'

        # Execute OCR
        ocr_result = image_ocr.ocr_image(sample_image_path, api_key="dummy_api_key")
        assert ocr_result is not None

        # Execute LLM Extraction on extracted text
        extracted = llm_model.extract_entities_json(str(ocr_result))
        assert extracted["name"] == "Client Corp"
        assert extracted["email"] == "contact@client.com"
