"""Integration tests explicitly opt into resetting the synthetic local stack."""

import os
import subprocess
import sys

import psycopg
import pytest

from scripts.client import ROOT


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration", action="store_true", help="Test and reset the local Compose lab"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--integration"):
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(
                    pytest.mark.skip(reason="requires --integration and a running stack")
                )


@pytest.fixture
def clean_lab() -> None:
    subprocess.run(
        [sys.executable, "-m", "scripts.fixtures", "reset"],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def service_db():
    with psycopg.connect(
        host="127.0.0.1",
        port=os.getenv("POSTGRES_PORT", "55432"),
        dbname="service_db",
        user="service_resource",
        password=os.environ["SERVICE_DB_PASSWORD"],
    ) as connection:
        yield connection
