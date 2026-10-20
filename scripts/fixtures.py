"""Explicit local fixture administration; never used by a resource service."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "reset"])
    args = parser.parse_args()
    tables = {
        "docs": "docs.documents",
        "requests": "support.notes, support.requests, support.tenants",
        "service": "runtime.features, settings.features, settings.tenants",
    }
    for name, resources in tables.items():
        sql = "BEGIN;\nSELECT pg_advisory_xact_lock(192837465);\n"
        sql += (
            "CREATE TABLE IF NOT EXISTS public.fixture_state "
            "(id boolean PRIMARY KEY DEFAULT true CHECK (id));\n"
        )
        if args.action == "reset":
            sql += f"TRUNCATE {resources};\n"
        fixture = (ROOT / f"data/seed/{name}.sql").read_text()
        if args.action == "seed":
            # Bootstrap-only marker preserves deletions as well as updates on repeat seeds.
            sql += "DO $seed$ BEGIN IF NOT EXISTS (SELECT 1 FROM public.fixture_state) THEN\n"
            sql += fixture + "\nINSERT INTO public.fixture_state VALUES (true);\n"
            sql += "END IF; END $seed$;\n"
        else:
            sql += (
                fixture
                + "\nINSERT INTO public.fixture_state VALUES (true) ON CONFLICT DO NOTHING;\n"
            )
        sql += "COMMIT;\n"
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "bootstrap",
                "-d",
                f"{name}_db",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=sql,
            text=True,
            check=True,
            cwd=ROOT,
        )
    print(f"Fixtures {args.action} complete.")


if __name__ == "__main__":
    main()
