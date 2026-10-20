import os

import psycopg
import pytest
from psycopg import sql

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("name", ["docs", "requests", "service"])
def test_database_isolation_and_no_ddl(name, clean_lab):
    def connect(database):
        return psycopg.connect(
            host="127.0.0.1",
            port=os.getenv("POSTGRES_PORT", "55432"),
            dbname=database,
            user=f"{name}_resource",
            password=os.environ[f"{name.upper()}_DB_PASSWORD"],
        )

    with connect(f"{name}_db") as db:
        assert db.execute("SELECT current_user").fetchone() == (f"{name}_resource",)
        for schema in [
            "public",
            {"docs": "docs", "requests": "support", "service": "settings"}[name],
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(
                    sql.SQL("CREATE TABLE {}.bypass (id int)").format(sql.Identifier(schema))
                )
            db.rollback()
    for other in ["docs_db", "requests_db", "service_db", "postgres", "template1"]:
        if other != f"{name}_db":
            with pytest.raises(psycopg.OperationalError, match="permission denied"):
                connect(other)
