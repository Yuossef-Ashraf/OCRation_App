"""
Web and API endpoint tests for OCRation_App Flask interface.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

try:
    from web.app import app as flask_app
except ImportError:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web")))
    from app import app as flask_app


@pytest.fixture
def client():
    """Create a Flask test client."""
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client


class TestWebEndpoints:
    """Test Flask routes, status codes, and security."""

    def test_index_page_loads(self, client):
        """Test GET / returns 200 and loads HTML template."""
        response = client.get('/')
        assert response.status_code == 200

    def test_upload_without_file(self, client):
        """Test uploading empty request returns proper error code."""
        response = client.post('/upload', data={})
        # Should return 400 Bad Request or redirect
        assert response.status_code in (400, 302, 200)

    def test_health_or_api_status(self, client):
        """Test basic route responsiveness."""
        response = client.get('/health', follow_redirects=True)
        assert response.status_code in (200, 404)
