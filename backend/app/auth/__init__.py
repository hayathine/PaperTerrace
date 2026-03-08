"""
Authentication module for PaperTerrace.
Provides Neon Auth-based authentication for the application.
"""

from .dependencies import (
    AuthenticatedUser,
    CurrentUser,
    OptionalUser,
    get_current_user,
    get_optional_user,
)

__all__ = [
    "AuthenticatedUser",
    "CurrentUser",
    "OptionalUser",
    "get_current_user",
    "get_optional_user",
]
