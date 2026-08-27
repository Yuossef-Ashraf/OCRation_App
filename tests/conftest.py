"""
Pytest configuration and shared fixtures for OCRation_App test suite.
"""

import os
import struct
import tempfile
import zlib
import pytest

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def _create_minimal_png(width: int = 200, height: int = 100) -> bytes:
    """Fallback generator for a minimal valid PNG image using standard library."""
    png = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff)
    png += struct.pack('>I', len(ihdr_data)) + b'IHDR' + ihdr_data + ihdr_crc
    raw_data = b''.join(b'\x00' + b'\xff\xff\xff' * width for _ in range(height))
    idat_data = zlib.compress(raw_data)
    idat_crc = struct.pack('>I', zlib.crc32(b'IDAT' + idat_data) & 0xffffffff)
    png += struct.pack('>I', len(idat_data)) + b'IDAT' + idat_data + idat_crc
    iend_crc = struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
    png += struct.pack('>I', 0) + b'IEND' + iend_crc
    return png


@pytest.fixture
def sample_image():
    """
    Creates a simple white 200x100 PNG image with black text 'Hello World' using Pillow.
    Saves to a temporary file, yields the path, and deletes it after the test.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    if PIL_AVAILABLE:
        try:
            img = Image.new("RGB", (200, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 40), "Hello World", fill=(0, 0, 0))
            img.save(temp_path, format="PNG")
        except Exception:
            with open(temp_path, "wb") as f:
                f.write(_create_minimal_png(200, 100))
    else:
        with open(temp_path, "wb") as f:
            f.write(_create_minimal_png(200, 100))

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@pytest.fixture
def mock_groq_response():
    """
    Returns a fake Groq API response dict with a translation result string 'مرحبا بالعالم'.
    """
    return {
        "id": "chatcmpl-test-id-12345",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "llama-3.3-70b-versatile",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "مرحبا بالعالم"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20
        }
    }
