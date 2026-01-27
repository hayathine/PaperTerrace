"""
Authentication dependencies for FastAPI.
Provides dependency injection for authenticated routes.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.auth.firebase import FirebaseAuth, FirebaseAuthError, get_firebase_auth
from src.logger import logger


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
    authorization: Annotated[str | None, Header()] = None,
    firebase_auth: FirebaseAuth = Depends(get_firebase_auth),
) -> AuthenticatedUser:
    """
    Dependency to get the current authenticated user.
    
    Extracts and verifies the Firebase ID token from the Authorization header.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"uid": user.uid, "email": user.email}
    """
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
            "User authenticated",
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
    authorization: Annotated[str | None, Header()] = None,
    firebase_auth: FirebaseAuth = Depends(get_firebase_auth),
) -> AuthenticatedUser | None:
    """
    Dependency to optionally get the current user.
    
    Returns None if no valid token is provided, instead of raising an error.
    Useful for routes that work differently for authenticated vs anonymous users.
    
    Usage:
        @app.get("/papers/{id}")
        async def get_paper(
            id: str, 
            user: AuthenticatedUser | None = Depends(get_optional_user)
        ):
            # If user is logged in, they can see their private papers
            # Otherwise, only public papers are visible
            ...
    """
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
