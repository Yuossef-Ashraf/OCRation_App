"""
Custom Exception Classes for OCRATION Application.
Provides clear, structured exceptions for OCR, LLM, and Web modules.
"""


class OCRationError(Exception):
    """Base exception for all OCRATION-related errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


# =====================================================================
# OCR & Image Processing Exceptions
# =====================================================================

class OCREngineError(OCRationError):
    """Raised when an error occurs during OCR processing."""
    pass


class OCRInvalidImageError(OCREngineError):
    """Raised when the input image is invalid, corrupted, or unsupported."""
    pass


class OCRAPIError(OCREngineError):
    """Raised when an external OCR API returns an error or fails."""
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        super().__init__(message, details)
        self.status_code = status_code


class OCRRateLimitError(OCRAPIError):
    """Raised when OCR API rate limits are exceeded."""
    pass


# =====================================================================
# LLM & Translation Exceptions
# =====================================================================

class LLMProviderError(OCRationError):
    """Base exception for LLM provider errors."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when LLM API keys are missing or invalid."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when LLM API rate limits are exceeded."""
    pass


class LLMResponseParsingError(LLMProviderError):
    """Raised when LLM response cannot be parsed."""
    pass


# =====================================================================
# Configuration & Validation Exceptions
# =====================================================================

class ConfigurationError(OCRationError):
    """Raised when configuration or environment variables are missing or invalid."""
    pass


class ValidationError(OCRationError):
    """Raised when user input validation fails."""
    pass
