"""PostgreSQL tests must resolve to a marked Docker container, never a host URL."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from tests.conftest import postgres_schema_url, postgres_test_url
from tests.support.postgres import docker_postgres_url

TEST_LABEL = {"io.biocypher.registry.test-database": "true"}


def inspect_result(*, labels=None, ports=True, running=True):
    return SimpleNamespace(
        stdout=json.dumps(
            [
                {
                    "Config": {"Labels": labels},
                    "State": {"Running": running},
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


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("Docker is not installed"),
        PermissionError("Docker socket is unavailable"),
        subprocess.CalledProcessError(1, ["docker", "inspect"]),
        subprocess.TimeoutExpired(["docker", "inspect"], 15),
    ],
    ids=[
        "missing-docker",
        "inaccessible-docker",
        "missing-container",
        "docker-timeout",
    ],
)
def test_postgres_fixture_skips_when_docker_is_unavailable(monkeypatch, error):
    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setenv("REGISTRY_TEST_POSTGRES_CONTAINER", "test-container")
    monkeypatch.setattr("tests.support.postgres.subprocess.run", unavailable)
    with pytest.raises(pytest.skip.Exception, match="Docker"):
        postgres_test_url.__wrapped__()


def test_postgres_fixture_skips_stopped_test_container(monkeypatch):
    monkeypatch.setenv("REGISTRY_TEST_POSTGRES_CONTAINER", "test-container")
    monkeypatch.setattr(
        "tests.support.postgres.subprocess.run",
        lambda *args, **kwargs: inspect_result(
            labels=TEST_LABEL, running=False, ports=False
        ),
    )
    with pytest.raises(pytest.skip.Exception, match="not running"):
        postgres_test_url.__wrapped__()


def test_postgres_fixture_skips_without_selecting_a_container(monkeypatch):
    monkeypatch.delenv("REGISTRY_TEST_POSTGRES_CONTAINER", raising=False)
    inspect = Mock(side_effect=AssertionError("Docker must not be inspected"))
    monkeypatch.setattr("tests.support.postgres.subprocess.run", inspect)
    with pytest.raises(pytest.skip.Exception, match="REGISTRY_TEST_POSTGRES_CONTAINER"):
        postgres_test_url.__wrapped__()
    inspect.assert_not_called()


def test_postgres_fixture_resolves_running_test_container(monkeypatch):
    monkeypatch.setenv("REGISTRY_TEST_POSTGRES_CONTAINER", "test-container")
    monkeypatch.setattr(
        "tests.support.postgres.subprocess.run",
        lambda *args, **kwargs: inspect_result(labels=TEST_LABEL),
    )
    url = make_url(postgres_test_url.__wrapped__())
    assert (url.host, url.port, url.database) == ("127.0.0.1", 55432, "registry_test")


@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        "[]",
        "{}",
        inspect_result(labels=TEST_LABEL, ports=False).stdout,
        inspect_result(labels={}).stdout,
    ],
    ids=[
        "invalid-json",
        "empty-inspection",
        "invalid-inspection",
        "no-port",
        "unmarked",
    ],
)
def test_postgres_fixture_does_not_skip_invalid_configuration(monkeypatch, response):
    monkeypatch.setenv("REGISTRY_TEST_POSTGRES_CONTAINER", "test-container")
    monkeypatch.setattr(
        "tests.support.postgres.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=response),
    )
    with pytest.raises(RuntimeError, match="configuration"):
        postgres_test_url.__wrapped__()


def test_postgres_fixture_does_not_skip_database_operation_errors(monkeypatch):
    database = Mock()
    database.begin.side_effect = OperationalError(
        "CREATE SCHEMA", {}, RuntimeError("Database operation failed")
    )
    monkeypatch.setattr("sqlalchemy.create_engine", Mock(return_value=database))
    schema = postgres_schema_url.__wrapped__(
        "postgresql://registry_test@127.0.0.1/test"
    )
    with pytest.raises(OperationalError, match="Database operation failed"):
        next(schema)
