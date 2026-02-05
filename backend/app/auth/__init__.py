"""
Authentication module for PaperTerrace.
Provides Firebase-based authentication for the application.
"""

from .dependencies import (
    AuthenticatedUser,
    CurrentUser,
    OptionalUser,
    get_current_user,
    get_optional_user,
)
from .firebase import FirebaseAuth, FirebaseAuthError, get_firebase_auth

__all__ = [
    "FirebaseAuth",
    "FirebaseAuthError",
    "get_firebase_auth",
    "AuthenticatedUser",
    "CurrentUser",
    "OptionalUser",
    "get_current_user",
    "get_optional_user",
]
