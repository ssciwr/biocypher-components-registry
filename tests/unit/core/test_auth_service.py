"""Device authentication contracts: verified identity, no retained user token."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from src.core.auth.models import AuthSession
from src.core.auth.service import (
    GitHubAuthenticationError,
    authenticate_github_device,
)

TOKEN = "test-user-token-must-not-leak"
DEVICE = "private-device-code-must-not-leak"


def response(payload=None, *, status=200):
    result = Mock(status_code=status)
    result.json.return_value = {} if payload is None else payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError("private response")
    return result


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_ID", "fixture-client")
    monkeypatch.setenv("GITHUB_OAUTH_CLIENT_SECRET", "fixture-secret")
    transport = Mock()
    transport.post.side_effect = [
        response(
            {
                "device_code": DEVICE,
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 2,
            }
        ),
        response({"access_token": TOKEN, "token_type": "bearer"}),
    ]
    transport.get.return_value = response({"id": 123, "login": "maintainer"})
    transport.delete.return_value = response(status=204)
    return transport


def authenticate(http, **kwargs):
    return authenticate_github_device(
        client_id=kwargs.pop("client_id", "fixture-client"),
        client_secret=kwargs.pop("client_secret", "fixture-secret"),
        http=http,
        on_authorization=kwargs.pop("on_authorization", Mock()),
        sleep=kwargs.pop("sleep", Mock()),
        monotonic=lambda: 0,
        **kwargs,
    )


def test_authentication_returns_only_verified_identity_and_revokes_specific_token(http):
    callback = Mock()
    actor = authenticate(http, on_authorization=callback)
    assert actor == AuthSession(github_user_id="123")
    assert TOKEN not in repr(actor)
    callback.assert_called_once_with("https://github.com/login/device", "ABCD-EFGH")
    assert http.get.call_args.args[0] == "https://api.github.com/user"
    assert http.get.call_args.kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert (
        http.delete.call_args.args[0]
        == "https://api.github.com/applications/fixture-client/token"
    )
    assert http.delete.call_args.kwargs["json"] == {"access_token": TOKEN}
    assert http.delete.call_args.kwargs["auth"] == ("fixture-client", "fixture-secret")
    # No broad grant revocation, registry API, or request without a timeout.
    for name, args, kwargs in http.mock_calls:
        if name in {"post", "get", "delete"}:
            assert kwargs.get("timeout") is not None


def test_pending_and_slow_down_obey_polling_interval(http):
    initial = response(
        {
            "device_code": DEVICE,
            "user_code": "ABCD",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 2,
        }
    )
    http.post.side_effect = [
        initial,
        response({"error": "authorization_pending"}),
        response({"error": "slow_down"}),
        response({"access_token": TOKEN}),
    ]
    sleep = Mock()
    assert authenticate(http, sleep=sleep).github_user_id == "123"
    intervals = [call.args[0] for call in sleep.call_args_list]
    assert len(intervals) >= 2
    assert intervals[-1] >= 7


@pytest.mark.parametrize(
    "error", ["access_denied", "expired_token", "incorrect_client_credentials"]
)
def test_authorization_failure_never_checks_identity(http, error):
    http.post.side_effect = [
        response(
            {
                "device_code": DEVICE,
                "user_code": "ABCD",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 1,
            }
        ),
        response({"error": error}),
    ]
    with pytest.raises(GitHubAuthenticationError) as exc:
        authenticate(http)
    assert TOKEN not in str(exc.value) and DEVICE not in str(exc.value)
    http.get.assert_not_called()
    http.delete.assert_not_called()


def test_identity_failure_still_revokes_token_and_sanitizes_error(http):
    http.get.side_effect = requests.ConnectionError(f"Authorization: Bearer {TOKEN}")
    with pytest.raises(GitHubAuthenticationError) as exc:
        authenticate(http)
    assert TOKEN not in str(exc.value)
    http.delete.assert_called_once()


def test_unconfirmed_revocation_does_not_return_an_actor(http):
    http.delete.side_effect = requests.ConnectionError(TOKEN)
    with pytest.raises(GitHubAuthenticationError) as exc:
        authenticate(http)
    assert TOKEN not in str(exc.value)
    assert "revok" in str(exc.value).lower()


def test_missing_configuration_fails_before_network(http):
    with pytest.raises(GitHubAuthenticationError):
        authenticate(http, client_secret="")
    assert not http.mock_calls


def test_identity_cancellation_attempts_revocation(http):
    http.get.side_effect = KeyboardInterrupt()
    with pytest.raises((KeyboardInterrupt, GitHubAuthenticationError)):
        authenticate(http)
    http.delete.assert_called_once()


def test_local_deadline_stops_polling_without_sleeping_past_expiry(http):
    http.post.side_effect = [
        response(
            {
                "device_code": DEVICE,
                "user_code": "ABCD",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 3,
                "interval": 2,
            }
        ),
        response({"error": "authorization_pending"}),
    ]
    now = [0.0]
    sleeps = []

    def advance(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    with pytest.raises(GitHubAuthenticationError):
        authenticate_github_device(
            client_id="fixture-client",
            client_secret="fixture-secret",
            on_authorization=Mock(),
            http=http,
            sleep=advance,
            monotonic=lambda: now[0],
        )
    assert now[0] == 3
    assert sleeps == [2, 1]
    assert http.post.call_count == 2
    http.get.assert_not_called()


def test_failed_identity_verification_does_not_leak_credentials_to_logs(
    http, caplog, capsys
):
    http.get.side_effect = requests.ConnectionError(f"Bearer {TOKEN} device {DEVICE}")
    with pytest.raises(GitHubAuthenticationError) as exc:
        authenticate(http)
    captured = capsys.readouterr()
    rendered = caplog.text + captured.out + captured.err + str(exc.value)
    assert TOKEN not in rendered
    assert DEVICE not in rendered


def test_successful_device_authentication_creates_no_credential_files(
    http, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert authenticate(http).github_user_id == "123"
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(
    "payload", [{}, {"id": None}, {"id": "123"}, {"id": -1}, {"id": True}]
)
def test_invalid_identity_is_rejected_and_token_revoked(http, payload):
    http.get.return_value = response(payload)
    with pytest.raises(GitHubAuthenticationError):
        authenticate(http)
    http.delete.assert_called_once()


@pytest.mark.parametrize("status", [200, 400])
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("device_flow_disabled", "Enable Device Flow"),
        ("incorrect_client_credentials", "GITHUB_OAUTH_CLIENT_ID"),
        ("access_denied", "denied"),
        ("expired_token", "expired"),
        ("unknown-provider-error", "rejected"),
    ],
)
def test_provider_errors_explain_next_step_without_exposing_payload(
    http, status, error, expected
):
    http.post.side_effect = [
        response(
            {"error": error, "error_description": f"{TOKEN} {DEVICE}"},
            status=status,
        )
    ]
    callback = Mock()
    with pytest.raises(GitHubAuthenticationError, match=expected) as exc:
        authenticate(http, on_authorization=callback)
    assert TOKEN not in str(exc.value) and DEVICE not in str(exc.value)
    callback.assert_not_called()
    http.get.assert_not_called()
    http.delete.assert_not_called()


@pytest.mark.parametrize("payload", [{}, [], {"device_code": DEVICE}])
def test_incomplete_device_response_has_specific_safe_error(http, payload):
    http.post.side_effect = [response(payload)]
    with pytest.raises(GitHubAuthenticationError, match="Invalid GitHub device"):
        authenticate(http)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (requests.Timeout(TOKEN), "timed out"),
        (requests.exceptions.SSLError(TOKEN), "TLS"),
        (requests.ConnectionError(TOKEN), "connect"),
    ],
)
def test_device_transport_failure_is_actionable_and_redacted(http, failure, expected):
    http.post.side_effect = failure
    with pytest.raises(GitHubAuthenticationError, match=expected) as exc:
        authenticate(http)
    assert TOKEN not in str(exc.value)


@pytest.mark.parametrize("status", [429, 500])
def test_device_http_failure_reports_only_status(http, status):
    http.post.side_effect = [response(status=status)]
    with pytest.raises(GitHubAuthenticationError, match=f"HTTP {status}"):
        authenticate(http)


def test_non_json_device_response_is_explained(http):
    invalid = response()
    invalid.json.side_effect = ValueError(TOKEN)
    http.post.side_effect = [invalid]
    with pytest.raises(GitHubAuthenticationError, match="invalid JSON") as exc:
        authenticate(http)
    assert TOKEN not in str(exc.value)
