"""
Neon Auth module.
Provides JWT verification using Neon Auth JWKS.
"""

import time
from functools import lru_cache
from typing import Any, Dict

import httpx
from jose import jwt

from app.core.config import get_neon_auth_jwks_url, get_neon_auth_url
from common.logger import ServiceLogger

log = ServiceLogger("NeonAuth")


class NeonAuthError(Exception):
    """Neon authentication error."""

    pass


class NeonAuth:
    """Neon Auth session verification using JWKS."""

    _instance = None
    _jwks_cache = None
    _jwks_last_fetch = 0
    _jwks_ttl = 3600  # 1 hour

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.jwks_url = get_neon_auth_jwks_url()
        self.auth_url = get_neon_auth_url()

        if not self.jwks_url:
            log.warning("init", "NEON_AUTH_JWKS_URL (or _DEV) is not set")

    async def _get_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Neon Auth or return cached version."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_last_fetch < self._jwks_ttl):
            return self._jwks_cache

        if not self.jwks_url:
            raise NeonAuthError("NEON_AUTH_JWKS_URL is not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_last_fetch = now
                log.info("jwks", "JWKS updated successfully")
                return self._jwks_cache
        except Exception as e:
            log.exception("jwks", "Failed to fetch JWKS", error=str(e))
            if self._jwks_cache:
                log.warning("jwks", "Using stale JWKS cache")
                return self._jwks_cache
            raise NeonAuthError(f"Could not fetch JWKS: {e}") from e

    async def verify_token(self, token: str) -> dict:
        """
        Verify a Neon Auth JWT.

        Args:
            token: The JWT to verify

        Returns:
            Decoded token containing user information

        Raises:
            NeonAuthError: If token verification fails
        """
        try:
            # First, get the unverified header to find the kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise NeonAuthError("No 'kid' found in token header")

            jwks = await self._get_jwks()

            # Find the correct key in JWKS
            rsa_key = {}
            for key in jwks.get("keys", []):
                if key["kid"] == kid:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"],
                    }
                    break

            if not rsa_key:
                raise NeonAuthError("Could not find appropriate key in JWKS")

            # Verify the JWT
            # Better Auth / Neon Auth JWTs usually have an 'iss' and 'aud'
            # For now, we skip detailed iss/aud check if not configured strictly,
            # but ideally we should check against NEON_AUTH_URL
            decoded_payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                options={
                    "verify_aud": False
                },  # Adjust based on Neon Auth actual JWT structure
            )

            log.debug(
                "verify_token",
                "Token verified successfully",
                sub=decoded_payload.get("sub"),
            )

            # Normalize the payload to match our AuthenticatedUser expectations
            # Better Auth uses 'sub' as user ID
            normalized_payload = {
                "uid": decoded_payload.get("sub"),
                "email": decoded_payload.get("email"),
                "email_verified": decoded_payload.get("email_verified", False),
                "name": decoded_payload.get("name"),
                "picture": decoded_payload.get("image"),  # Better Auth uses 'image'
                "provider": "neon_auth",
            }

            return normalized_payload

        except jwt.ExpiredSignatureError as e:
            log.warning("verify_token", "Expired token")
            raise NeonAuthError("Token has expired") from e
        except jwt.JWTClaimsError as e:
            log.warning("verify_token", "Invalid claims", error=str(e))
            raise NeonAuthError("Token claims are invalid") from e
        except Exception as e:
            log.exception("verify_token", "Token verification failed", error=str(e))
            raise NeonAuthError(f"Token verification failed: {e}") from e


@lru_cache
def get_neon_auth() -> NeonAuth:
    """Get the singleton NeonAuth instance."""
    return NeonAuth()
