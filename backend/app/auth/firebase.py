"""
Firebase Authentication module.
Provides Firebase Admin SDK initialization and token verification.
"""

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from common.logger import logger


class FirebaseAuthError(Exception):
    """Firebase authentication error."""

    pass


class FirebaseAuth:
    """Firebase Admin SDK wrapper for authentication."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not FirebaseAuth._initialized:
            self._initialize()
            FirebaseAuth._initialized = True

    def _initialize(self):
        """Initialize Firebase Admin SDK."""
        # Check if already initialized
        if firebase_admin._apps:
            logger.info("Firebase already initialized")
            return

        # Try to load credentials from environment or file
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        project_id = os.getenv("FIREBASE_PROJECT_ID", "paperterrace")

        try:
            if cred_path and os.path.exists(cred_path):
                # Load from service account JSON file
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"projectId": project_id})
                logger.info(
                    "Firebase initialized with service account",
                    extra={"project_id": project_id},
                )
            else:
                # Use Application Default Credentials (for Cloud Run)
                firebase_admin.initialize_app(options={"projectId": project_id})
                logger.info(
                    "Firebase initialized with default credentials",
                    extra={"project_id": project_id},
                )
        except Exception as e:
            logger.exception(
                "Failed to initialize Firebase",
                extra={"error": str(e)},
            )
            raise FirebaseAuthError(f"Firebase initialization failed: {e}") from e

    def verify_token(self, id_token: str) -> dict:
        """
        Verify a Firebase ID token.

        Args:
            id_token: The Firebase ID token to verify

        Returns:
            Decoded token containing user information

        Raises:
            FirebaseAuthError: If token verification fails
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            logger.debug(
                "Token verified successfully",
                extra={"uid": decoded_token.get("uid")},
            )
            return decoded_token
        except auth.ExpiredIdTokenError as e:
            logger.warning("Expired token", extra={"error": str(e)})
            raise FirebaseAuthError("Token has expired") from e
        except auth.RevokedIdTokenError as e:
            logger.warning("Revoked token", extra={"error": str(e)})
            raise FirebaseAuthError("Token has been revoked") from e
        except auth.InvalidIdTokenError as e:
            logger.warning("Invalid token", extra={"error": str(e)})
            raise FirebaseAuthError("Invalid token") from e
        except Exception as e:
            logger.exception("Token verification failed", extra={"error": str(e)})
            raise FirebaseAuthError(f"Token verification failed: {e}") from e

    def get_user(self, uid: str) -> auth.UserRecord:
        """
        Get user information from Firebase.

        Args:
            uid: The user's Firebase UID

        Returns:
            UserRecord containing user information
        """
        try:
            user = auth.get_user(uid)
            logger.debug("User retrieved", extra={"uid": uid})
            return user
        except auth.UserNotFoundError as e:
            logger.warning("User not found", extra={"uid": uid})
            raise FirebaseAuthError("User not found") from e
        except Exception as e:
            logger.exception("Failed to get user", extra={"uid": uid, "error": str(e)})
            raise FirebaseAuthError(f"Failed to get user: {e}") from e

    def create_custom_token(self, uid: str, claims: dict | None = None) -> bytes:
        """
        Create a custom token for a user.

        Args:
            uid: The user's UID
            claims: Optional custom claims to include

        Returns:
            Custom token bytes
        """
        try:
            token = auth.create_custom_token(uid, claims)
            logger.debug("Custom token created", extra={"uid": uid})
            return token
        except Exception as e:
            logger.exception(
                "Failed to create custom token",
                extra={"uid": uid, "error": str(e)},
            )
            raise FirebaseAuthError(f"Failed to create custom token: {e}") from e


@lru_cache
def get_firebase_auth() -> FirebaseAuth:
    """Get the singleton FirebaseAuth instance."""
    return FirebaseAuth()
