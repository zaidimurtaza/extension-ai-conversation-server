import secrets
import string
import time
import urllib.parse

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth.google_auth import verify_google_id_token
from app.auth.token_manager import (
    FRONTEND_REDIRECT_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    JWT_ALGO,
    JWT_SECRET,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_superadmin,
    require_roles,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "openid email profile"

# In-memory one-time codes: code -> { accessToken, refreshToken, created_at }; 40s TTL
CODE_CHARS = string.ascii_lowercase + string.digits
CODE_TTL_SEC = 40
_auth_codes: dict[str, dict] = {}


def _make_auth_code() -> str:
    return "".join(secrets.choice(CODE_CHARS) for _ in range(6))


def _clean_expired_codes() -> None:
    now = time.time()
    expired = [c for c, v in _auth_codes.items() if (now - v["created_at"]) > CODE_TTL_SEC]
    for c in expired:
        del _auth_codes[c]


@router.get("/login")
def login():
    """Server-only OAuth: redirect to Google, then callback redirects to frontend with tokens."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": f"{SCOPE}",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google redirects here with ?code=...; exchange for id_token, issue our tokens, redirect to frontend."""
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    with httpx.Client() as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to exchange code for token")

    data = resp.json()
    id_token_str = data.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=401, detail="No id_token in response")

    # Google OAuth tokens to store in accounts.tokens
    expires_in = data.get("expires_in", 3600)
    google_tokens = {
        "expires_at": int(time.time()) + expires_in,
        "token_type": "bearer",
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
    }

    google_user = verify_google_id_token(id_token_str)
    email = google_user.get("email", "") or ""
    provider_account_id = google_user["sub"]

    # Only issue tokens with our internal users.id; never use Google sub
    if not email:
        redirect_url = f"{FRONTEND_REDIRECT_URL}?error=no_email"
        return RedirectResponse(url=redirect_url, status_code=302)

    from app.db.queries import (
        get_user_by_email,
        create_user,
        get_account,
        create_account,
        update_account_tokens,
    )

    try:
        db_user = get_user_by_email(email)
        if not db_user:
            create_user(email, google_user.get("name"), google_user.get("picture"))
            db_user = get_user_by_email(email)
        if not db_user:
            redirect_url = f"{FRONTEND_REDIRECT_URL}?error=login_failed"
            return RedirectResponse(url=redirect_url, status_code=302)
        account = get_account("google", provider_account_id)
        if not account:
            create_account(db_user["id"], "google", provider_account_id, tokens=google_tokens)
        else:
            update_account_tokens("google", provider_account_id, google_tokens)
    except Exception:
        redirect_url = f"{FRONTEND_REDIRECT_URL}?error=login_failed"
        return RedirectResponse(url=redirect_url, status_code=302)

    user_id = str(db_user["id"])  # always our internal users.id
    role = db_user.get("role") or "user"

    access = create_access_token(user_id, email, role=role)
    refresh = create_refresh_token(user_id, email, role=role)

    _clean_expired_codes()
    code = _make_auth_code()
    _auth_codes[code] = {
        "accessToken": access,
        "refreshToken": refresh,
        "created_at": time.time(),
    }
    redirect_url = f"{FRONTEND_REDIRECT_URL}?code={code}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/tokens")
def exchange_code_for_tokens(code: str):
    """
    One-time exchange: pass the 6-char code from redirect; returns access + refresh.
    Code expires in 40s and is deleted after successful use.
    """
    _clean_expired_codes()
    if code not in _auth_codes:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    entry = _auth_codes[code]
    if (time.time() - entry["created_at"]) > CODE_TTL_SEC:
        del _auth_codes[code]
        raise HTTPException(status_code=400, detail="Code expired")
    del _auth_codes[code]
    return {
        "access_token": entry["accessToken"],
        "refresh_token": entry["refreshToken"],
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(data: dict):
    """Exchange refresh_token for new access + refresh (rotation)."""
    token = data.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token required")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Wrong token type")

    user_id = payload["sub"]
    email = payload.get("email", "")
    role = payload.get("role", "user")

    new_access = create_access_token(user_id, email, role=role)
    new_refresh = create_refresh_token(user_id, email, role=role)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    """Protected: requires Bearer access token."""
    return {
        "user_id": user["sub"],
        "email": user.get("email", ""),
        "role": user.get("role", "user"),
    }


@router.get("/admin-only")
def admin_only(user=Depends(require_roles(["superadmin"]))):
    """Only superadmin can access. Users get 403."""
    return {"message": "Superadmin only", "user_id": user["sub"], "role": user["role"]}
