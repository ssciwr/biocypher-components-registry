"""Resolve PostgreSQL tests only to an explicitly marked Docker container."""

import json
import subprocess

from sqlalchemy.engine import URL


class PostgresTestUnavailable(RuntimeError):
    """Docker or the selected PostgreSQL test container is unavailable."""


def docker_postgres_url(container: str) -> str:
    """Use Docker's published port; never accept an arbitrary database URL."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--", container],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        raise PostgresTestUnavailable(
            "Docker PostgreSQL is unavailable or the test container does not exist. "
            "Start docker-compose.test.yml to run PostgreSQL tests."
        ) from None

    try:
        details = json.loads(result.stdout)[0]
        config = details["Config"]
        if (config.get("Labels") or {}).get(
            "io.biocypher.registry.test-database"
        ) != "true":
            raise ValueError("Container is not marked as a registry test database.")
        if not details["State"]["Running"]:
            raise PostgresTestUnavailable(
                "Docker PostgreSQL test container is not running. "
                "Start docker-compose.test.yml to run PostgreSQL tests."
            )
        ports = details["NetworkSettings"]["Ports"]["5432/tcp"]
        port = int(ports[0]["HostPort"])
        if not 1 <= port <= 65535:
            raise ValueError("Invalid Docker PostgreSQL port.")
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(
            "Docker PostgreSQL test container configuration is invalid or not marked "
            "for tests. Check its test label and published PostgreSQL port."
        ) from None
    return URL.create(
        "postgresql+psycopg2",
        username="registry_test",
        password="registry_test",
        host="127.0.0.1",
        port=port,
        database="registry_test",
    ).render_as_string(hide_password=False)
