"""
Authentication dependencies for FastAPI.
Provides dependency injection for authenticated routes.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.auth.firebase import FirebaseAuth, FirebaseAuthError, get_firebase_auth
from common.logger import logger


class AuthenticatedUser:
    """Represents an authenticated user from Firebase."""

    def __init__(self, decoded_token: dict):
        self.uid: str = decoded_token.get("uid", "")
        self.email: str = decoded_token.get("email", "")
        self.email_verified: bool = decoded_token.get("email_verified", False)
        self.name: str = decoded_token.get("name", "")
        self.picture: str = decoded_token.get("picture", "")
        self.provider: str = decoded_token.get("firebase", {}).get(
            "sign_in_provider", ""
        )
        self._raw_token = decoded_token

    def __repr__(self):
        return f"AuthenticatedUser(uid={self.uid}, email={self.email})"


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    firebase_auth: FirebaseAuth = Depends(get_firebase_auth),
) -> AuthenticatedUser:
    """
    Dependency to get the current authenticated user.

    Supports both trusted proxy (API Gateway) and direct token verification.
    """
    # 1. Check if authenticated at the Edge (Cloudflare Gateway)
    # Note: request.state.user_id is set by TrustedProxyMiddleware in main.py
    user_id = getattr(request.state, "user_id", None)

    # If it's a guest, treat as unauthenticated for this dependency
    if user_id and not user_id.startswith("guest_"):
        decoded_token = {
            "uid": user_id,
            "email": request.headers.get("X-User-Email", ""),
            "name": request.headers.get("X-User-Name", ""),
            "picture": request.headers.get("X-User-Picture", ""),
            "email_verified": request.headers.get("X-User-Email-Verified") == "true",
            "firebase": {
                "sign_in_provider": request.headers.get("X-User-Provider", "")
            },
        }
        return AuthenticatedUser(decoded_token)

    # 2. Traditional Authorization Header (Local Dev / Direct Hit)
    if not authorization:
        logger.debug("No authorization header provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug("Invalid authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効な認証形式です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        decoded_token = firebase_auth.verify_token(token)
        user = AuthenticatedUser(decoded_token)
        logger.info(
            "User authenticated via token",
            extra={"uid": user.uid, "email": user.email, "provider": user.provider},
        )
        return user
    except FirebaseAuthError as e:
        logger.warning("Authentication failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    firebase_auth: FirebaseAuth = Depends(get_firebase_auth),
) -> AuthenticatedUser | None:
    """
    Dependency to optionally get the current user.
    """
    # 1. Trusted Proxy Check
    user_id = getattr(request.state, "user_id", None)
    if user_id and not user_id.startswith("guest_"):
        decoded_token = {
            "uid": user_id,
            "email": request.headers.get("X-User-Email", ""),
            "name": request.headers.get("X-User-Name", ""),
            "picture": request.headers.get("X-User-Picture", ""),
            "email_verified": request.headers.get("X-User-Email-Verified") == "true",
            "firebase": {
                "sign_in_provider": request.headers.get("X-User-Provider", "")
            },
        }
        return AuthenticatedUser(decoded_token)

    # 2. Direct Authentication
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]

    try:
        decoded_token = firebase_auth.verify_token(token)
        return AuthenticatedUser(decoded_token)
    except FirebaseAuthError:
        return None


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]
