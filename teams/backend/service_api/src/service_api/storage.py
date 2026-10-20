"""Each operation owns a short transaction; no standing privileged connection."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connect() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.Connection[dict[str, Any]].connect(
        os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=3
    ) as connection:
        yield connection


def check_database() -> bool:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
