"""JWT verification for Supabase-issued tokens.

Supabase signs access tokens with HS256 using the project's JWT secret.
Set JOB_COPILOT_SUPABASE_JWT_SECRET to the value from:
  Supabase Dashboard → Project Settings → API → JWT Secret
"""

from __future__ import annotations

from fastapi import HTTPException, status

from ..config import settings


def verify_token(token: str) -> str:
    """Return the user_id (sub claim) for a valid Supabase JWT.

    Raises HTTP 401 on any validation failure.
    """
    try:
        from jose import JWTError, jwt

        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no sub claim")
        return user_id
    except ImportError:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "python-jose is not installed — add it to dependencies",
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"Token verification failed: {exc}",
        ) from exc
