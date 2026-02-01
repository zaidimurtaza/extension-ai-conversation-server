from typing import Optional, Dict, Any
from app.db.postgress import execute_query, execute_insert, execute_update


# --- Auth: users & accounts (find-or-create for OAuth) ---


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Return user row as dict or None."""
    rows = execute_query(
        "SELECT * FROM users WHERE email = %s",
        (email,),
        return_type="dict",
    )
    return rows[0] if rows else None


def create_user(email: str, name: Optional[str] = None, image: Optional[str] = None) -> int:
    """Insert user, return id."""
    user_id = execute_insert(
        "INSERT INTO users (email, name, image, email_verified) VALUES (%s, %s, %s, NOW()) RETURNING id",
        (email, name, image),
    )
    return user_id


def get_account(provider: str, provider_account_id: str) -> Optional[Dict[str, Any]]:
    """Return account row as dict or None."""
    rows = execute_query(
        "SELECT * FROM accounts WHERE provider = %s AND provider_account_id = %s",
        (provider, provider_account_id),
        return_type="dict",
    )
    return rows[0] if rows else None


def create_account(
    user_id: int,
    provider: str,
    provider_account_id: str,
    tokens: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert account. tokens stored as jsonb."""
    import json

    execute_insert(
        "INSERT INTO accounts (user_id, provider, provider_account_id, tokens) VALUES (%s, %s, %s, %s)",
        (user_id, provider, provider_account_id, json.dumps(tokens) if tokens else None),
    )


def update_account_tokens(
    provider: str,
    provider_account_id: str,
    tokens: Dict[str, Any],
) -> int:
    """Update account tokens (e.g. after OAuth refresh). Returns row count."""
    import json

    return execute_update(
        "UPDATE accounts SET tokens = %s WHERE provider = %s AND provider_account_id = %s",
        (json.dumps(tokens), provider, provider_account_id),
    )

def log_llm_call(
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    user_id: int,
) -> Optional[Any]:
    """Log an LLM call to the database. created_at uses DB default."""
    return execute_insert(
        "INSERT INTO llm_calls (model, tokens_in, tokens_out, cost, user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (model, tokens_in, tokens_out, cost, user_id),
    )