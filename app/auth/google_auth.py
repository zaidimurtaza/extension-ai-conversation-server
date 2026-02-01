from fastapi import HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.auth.token_manager import GOOGLE_CLIENT_ID


def verify_google_id_token(token: str):
    try:
        return id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")
