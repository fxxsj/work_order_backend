"""
Error codes returned to the frontend.

CRITICAL: Do not change any existing string values; they are part of the public API.
"""

from enum import Enum


class ErrorCodes(str, Enum):
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    BUSINESS_LOGIC_ERROR = "BUSINESS_LOGIC_ERROR"
    VERSION_CONFLICT = "VERSION_CONFLICT"

