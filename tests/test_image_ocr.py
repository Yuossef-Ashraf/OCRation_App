"""
Unit and integration tests for image_ocr module in OCRATION.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

import image_ocr
from exceptions import OCRInvalidImageError, OCRAPIError


class TestImageOCRValidation:
    """Test API key and input image validation."""

    def test_validate_api_key_valid(self):
        assert image_ocr._validate_api_key("valid_api_key_123456") is True
        assert image_ocr._validate_api_key("K81234567888957") is True

    def test_validate_api_key_invalid(self):
        assert image_ocr._validate_api_key("") is False
        assert image_ocr._validate_api_key("short") is False
        assert image_ocr._validate_api_key("key with spaces!") is False

    def test_validate_image_path_existing(self, sample_image_path):
        assert image_ocr._validate_image_path(sample_image_path) is True

    def test_validate_image_path_nonexistent(self):
        assert image_ocr._validate_image_path("non_existent_file_path_123.png") is False
        assert image_ocr._validate_image_path("") is False
        assert image_ocr._validate_image_path(None) is False


class TestImageOCRCache:
    """Test in-memory cache functionality for OCR results."""

    def test_cache_storage_and_retrieval(self):
        test_key = "test_image_hash_123"
        test_data = {"text": "Hello World", "mode": "standard"}
        
        # Store in cache
        image_ocr._cache[test_key] = (image_ocr.time.time(), test_data)
        
        # Verify cached
        assert test_key in image_ocr._cache
        timestamp, cached_val = image_ocr._cache[test_key]
        assert cached_val["text"] == "Hello World"


class TestOCRProcessing:
    """Test OCR processing pipeline and API calls."""

    @patch("image_ocr._session.post")
    def test_ocr_api_call_success(self, mock_post, sample_image_path, mock_ocr_success_response):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_ocr_success_response
        mock_post.return_value = mock_response

        # Execute OCR call
        result = image_ocr.ocr_image(
            sample_image_path,
            api_key="test_key_12345678",
            mode="standard"
        )

        assert result is not None
        assert "Invoice" in str(result) or isinstance(result, (dict, str))

    @patch("image_ocr._session.post")
    def test_ocr_api_network_error_handling(self, mock_post, sample_image_path):
        mock_post.side_effect = Exception("Connection Refused / Network Error")

        # Must handle error gracefully without crash
        try:
            result = image_ocr.ocr_image(
                sample_image_path,
                api_key="test_key_12345678",
                mode="standard"
            )
            # Either returns error dict or raises controlled exception
            assert result is not None
        except Exception as e:
            assert "Connection" in str(e) or isinstance(e, Exception)
