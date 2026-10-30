"""Resolve PostgreSQL tests only to an explicitly marked Docker container."""

import json
import subprocess

from sqlalchemy.engine import URL


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
        details = json.loads(result.stdout)[0]
        config = details["Config"]
        if (config.get("Labels") or {}).get(
            "io.biocypher.registry.test-database"
        ) != "true":
            raise ValueError("Container is not marked as a registry test database.")
        if not details["State"]["Running"]:
            raise ValueError("Docker PostgreSQL test container is not running.")
        ports = details["NetworkSettings"]["Ports"]["5432/tcp"]
        port = int(ports[0]["HostPort"])
    except (
        OSError,
        subprocess.SubprocessError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        raise RuntimeError(
            "Docker PostgreSQL test database is unavailable or not marked for tests. "
            "Start docker-compose.test.yml and set REGISTRY_TEST_POSTGRES_CONTAINER."
        ) from None
    return URL.create(
        "postgresql+psycopg2",
        username="registry_test",
        password="registry_test",
        host="127.0.0.1",
        port=port,
        database="registry_test",
    ).render_as_string(hide_password=False)
