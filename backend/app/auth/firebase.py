"""
Firebase Authentication module.
Provides Firebase Admin SDK initialization and token verification.
"""

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from common.logger import ServiceLogger

log = ServiceLogger("Firebase")


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
            log.info("initialize", "Firebase already initialized")
            return

        # Try to load credentials from environment or file
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        project_id = os.getenv("FIREBASE_PROJECT_ID", "paperterrace")

        try:
            if cred_path and os.path.exists(cred_path):
                # Load from service account JSON file
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"projectId": project_id})
                log.info(
                    "initialize",
                    "Firebase initialized with service account",
                    project_id=project_id,
                )
            else:
                # Use Application Default Credentials (for Cloud Run)
                firebase_admin.initialize_app(options={"projectId": project_id})
                log.info(
                    "initialize",
                    "Firebase initialized with default credentials",
                    project_id=project_id,
                )
        except Exception as e:
            log.exception(
                "initialize",
                "Failed to initialize Firebase",
                error=str(e),
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
            log.debug(
                "verify_token",
                "Token verified successfully",
                uid=decoded_token.get("uid"),
            )
            return decoded_token
        except auth.ExpiredIdTokenError as e:
            log.warning("verify_token", "Expired token", error=str(e))
            raise FirebaseAuthError("Token has expired") from e
        except auth.RevokedIdTokenError as e:
            log.warning("verify_token", "Revoked token", error=str(e))
            raise FirebaseAuthError("Token has been revoked") from e
        except auth.InvalidIdTokenError as e:
            log.warning("verify_token", "Invalid token", error=str(e))
            raise FirebaseAuthError("Invalid token") from e

        except Exception as e:
            log.exception("verify_token", "Token verification failed", error=str(e))
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
            log.debug("get_user", "User retrieved", uid=uid)
            return user
        except auth.UserNotFoundError as e:
            log.warning("get_user", "User not found", uid=uid)
            raise FirebaseAuthError("User not found") from e
        except Exception as e:
            log.exception("get_user", "Failed to get user", uid=uid, error=str(e))
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
            log.debug("create_custom_token", "Custom token created", uid=uid)
            return token
        except Exception as e:
            log.exception(
                "create_custom_token",
                "Failed to create custom token",
                uid=uid,
                error=str(e),
            )
            raise FirebaseAuthError(f"Failed to create custom token: {e}") from e


@lru_cache
def get_firebase_auth() -> FirebaseAuth:
    """Get the singleton FirebaseAuth instance."""
    return FirebaseAuth()
