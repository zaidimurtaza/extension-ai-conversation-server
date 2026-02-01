import os
import time
from typing import List, Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret")

GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL", "https://murtaza-projects.vercel.app")
JWT_ALGO = "HS256"

ACCESS_EXP = 15 * 60  # 15 min
REFRESH_EXP = 7 * 24 * 60 * 60  # 7 days

DEFAULT_ROLE = "user"


def create_access_token(user_id: str, email: str, role: str = DEFAULT_ROLE) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + ACCESS_EXP,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_refresh_token(user_id: str, email: str, role: str = DEFAULT_ROLE) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "refresh",
        "iat": int(time.time()),
        "exp": int(time.time()) + REFRESH_EXP,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Require Bearer token. Returns 401 if missing or invalid (so client gets auth error, not 422)."""
    if not authorization or not authorization.strip().startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise ValueError("No token")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        if "role" not in payload:
            payload["role"] = DEFAULT_ROLE
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid access token")


def require_roles(allowed_roles: List[str]):
    """Dependency: require current user's role to be in allowed_roles (e.g. superadmin-only)."""

    def _(user=Depends(get_current_user)):
        role = user.get("role", DEFAULT_ROLE)
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _


# Convenience dependencies for route protection
get_current_superadmin = require_roles(["superadmin"])
get_current_admin_or_superadmin = require_roles(["admin", "superadmin"])