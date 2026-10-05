"""PostgreSQL connection pool (psycopg 3) with pgvector support."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings


def _configure(conn: psycopg.Connection) -> None:
    # The vector type exists only after migrations; health checks must still work before that.
    try:
        register_vector(conn)
        conn.commit()
    except psycopg.Error:
        conn.rollback()


@lru_cache(maxsize=1)
def pool() -> ConnectionPool:
    p = ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        configure=_configure,
        open=False,
    )
    p.open(wait=False)
    return p


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


def ping() -> bool:
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def close_pool() -> None:
    if pool.cache_info().currsize:
        pool().close()
        pool.cache_clear()
