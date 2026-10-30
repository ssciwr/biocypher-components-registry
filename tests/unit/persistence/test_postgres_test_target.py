"""PostgreSQL tests must resolve to a marked Docker container, never a host URL."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from tests.support.postgres import docker_postgres_url


def inspect_result(*, labels=None, ports=True):
    return SimpleNamespace(
        stdout=json.dumps(
            [
                {
                    "Config": {"Labels": labels},
                    "State": {"Running": True},
                    "NetworkSettings": {
                        "Ports": {
                            "5432/tcp": [{"HostPort": "55432"}] if ports else None
                        }
                    },
                }
            ]
        )
    )


def test_postgres_target_uses_port_of_marked_docker_container(monkeypatch):
    def inspect(arguments, **kwargs):
        assert arguments == ["docker", "inspect", "--", "test-container"]
        return inspect_result(labels={"io.biocypher.registry.test-database": "true"})

    monkeypatch.setattr("tests.support.postgres.subprocess.run", inspect)
    url = make_url(docker_postgres_url("test-container"))
    assert (url.host, url.port, url.database) == ("127.0.0.1", 55432, "registry_test")


@pytest.mark.parametrize(
    "labels", [None, {}, {"io.biocypher.registry.test-database": "false"}]
)
def test_postgres_target_rejects_application_containers(monkeypatch, labels):
    monkeypatch.setattr(
        "tests.support.postgres.subprocess.run",
        lambda *args, **kwargs: inspect_result(labels=labels),
    )
    with pytest.raises(RuntimeError, match="not marked"):
        docker_postgres_url("application-container")


def test_postgres_target_never_falls_back_when_docker_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("Docker unavailable")

    monkeypatch.setattr("tests.support.postgres.subprocess.run", unavailable)
    with pytest.raises(RuntimeError, match="Docker PostgreSQL"):
        docker_postgres_url("test-container")
