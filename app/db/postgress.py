import os
import logging
from typing import Optional, List, Dict, Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_write_pool: Optional[ConnectionPool] = None
_read_pool: Optional[ConnectionPool] = None


def _get_conninfo(read_only: bool = False) -> str:
    """Build connection info string"""
    user = os.getenv("POSTGRES_USER_READ_ONLY" if read_only else "POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD_READ_ONLY" if read_only else "POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB")
    return f"host={host} port={port} dbname={dbname} user={user} password={password} sslmode=require"


def init_pools() -> None:
    """Initialize connection pools. Read pool only if POSTGRES_USER_READ_ONLY is set."""
    global _write_pool, _read_pool
    if _write_pool is not None:
        logger.debug("Database connection pools already initialized")
        return

    logger.info("Initializing database connection pools")
    _write_pool = ConnectionPool(
        _get_conninfo(read_only=False),
        min_size=5,
        max_size=50,
        timeout=60,
        open=False,
    )
    _write_pool.open()

    read_user = os.getenv("POSTGRES_USER_READ_ONLY")
    read_password = os.getenv("POSTGRES_PASSWORD_READ_ONLY")
    if read_user and read_password:
        _read_pool = ConnectionPool(
            _get_conninfo(read_only=True),
            min_size=5,
            max_size=50,
            timeout=60,
            open=False,
        )
        _read_pool.open()
        logger.info("Database connection pools ready (write + read)")
    else:
        _read_pool = None
        logger.info("Database connection pool ready (write only; no read-only user configured)")


def close_pools() -> None:
    """Close connection pools at shutdown"""
    global _write_pool, _read_pool
    if _write_pool:
        _write_pool.close()
    if _read_pool:
        _read_pool.close()
    logger.info("Database connection pools closed")


def execute_query(
    query: str,
    params: Optional[tuple] = None,
    return_type: str = "list",
    session_vars: Optional[Dict[str, Any]] = None,
    read_only: bool = False,
) -> List[Any]:
    """Execute a query and return the results. Falls back to write pool if read pool not configured."""
    if _write_pool is None:
        init_pools()
    pool = (_read_pool if read_only else _write_pool) or _write_pool

    with pool.connection() as connection:
        with connection.cursor(row_factory=dict_row if return_type == "dict" else None) as cursor:
            try:
                if session_vars:
                    for key, value in session_vars.items():
                        logger.debug("Setting %s to %s", key, value)
                        cursor.execute(f"SET {key} = %s", (value,))
                if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("WITH"):
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    logger.debug("Query executed successfully: %s...", query[:100])
                    if return_type == "dict":
                        return [dict(row) for row in results]
                    return list(results)
                cursor.execute(query, params)
                connection.commit()
                logger.debug("Query executed successfully: %s...", query[:100])
                return []
            except Exception as e:
                connection.rollback()
                logger.debug("Transaction rolled back")
                logger.error("Error executing query: %s", e)
                raise


def execute_insert(query: str, params: Optional[tuple] = None) -> Any:
    """Execute an INSERT and return first column of first row if RETURNING, else True/False."""
    if _write_pool is None:
        init_pools()
    with _write_pool.connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(query, params)
                if "RETURNING" in query.upper():
                    result = cursor.fetchone()
                    connection.commit()
                    logger.debug("INSERT executed successfully: %s...", query[:100])
                    return result[0] if result else None
                connection.commit()
                logger.debug("INSERT executed successfully: %s...", query[:100])
                return cursor.rowcount > 0
            except Exception as e:
                connection.rollback()
                logger.debug("Transaction rolled back")
                logger.error("Error executing insert: %s", e)
                raise


def execute_bulk_insert(query: str, rows: List[tuple], page_size: int = 1000) -> None:
    """Execute bulk insert using executemany."""
    if not rows:
        logger.info("No rows to insert.")
        return
    if _write_pool is None:
        init_pools()
    with _write_pool.connection() as connection:
        with connection.cursor() as cursor:
            try:
                for i in range(0, len(rows), page_size):
                    batch = rows[i : i + page_size]
                    cursor.executemany(query, batch)
                connection.commit()
                logger.debug("Bulk insert successful: %s rows.", len(rows))
            except Exception as e:
                connection.rollback()
                logger.error("Error executing bulk insert: %s", e)
                raise


def execute_update(query: str, params: Optional[tuple] = None) -> int:
    """Execute an UPDATE and return number of rows updated."""
    if not query.strip().upper().startswith("UPDATE"):
        raise ValueError("Only UPDATE queries are allowed in execute_update.")
    if _write_pool is None:
        init_pools()
    with _write_pool.connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(query, params)
                row_count = cursor.rowcount
                connection.commit()
                logger.debug("UPDATE executed successfully: %s... (%s rows)", query[:100], row_count)
                return row_count
            except Exception as e:
                connection.rollback()
                logger.debug("Transaction rolled back")
                logger.error("Error executing UPDATE: %s", e)
                raise


def build_session_vars(**kwargs) -> Dict[str, str]:
    """Build session variables with app. prefix"""
    return {f"app.{key}": value for key, value in kwargs.items()}

