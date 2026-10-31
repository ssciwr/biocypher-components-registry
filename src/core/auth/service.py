"""GitHub identity verification and temporary device authorization.

No credentials are persisted. Authentication completes only after the individual
access token has been revoked; callers receive a verified identity, never a token.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

import requests

from src.core.auth.models import AuthSession

_TIMEOUT = 10
_ACCEPT = {"Accept": "application/json"}


class GitHubAuthenticationError(Exception):
    """A sanitized authentication error safe to show in either interface."""


_DEVICE_ERRORS = {
    "device_flow_disabled": (
        "GitHub device flow is disabled for this OAuth app. In GitHub Settings > "
        "Developer settings > OAuth Apps, select the app matching "
        "GITHUB_OAUTH_CLIENT_ID and check Enable Device Flow, then retry."
    ),
    "incorrect_client_credentials": (
        "GitHub rejected the OAuth app credentials. Check GITHUB_OAUTH_CLIENT_ID "
        "matches your OAuth app."
    ),
    "access_denied": "GitHub authorization was denied. Run the command again to retry.",
    "expired_token": "GitHub authorization expired. Run the command again to retry.",
    "incorrect_device_code": (
        "GitHub rejected the device code. Run the command again to retry."
    ),
    "unsupported_grant_type": "GitHub rejected the device authorization grant type.",
}


def _device_response(response: Any, *, polling: bool = False) -> dict[str, Any]:
    """Interpret provider errors without displaying untrusted response contents."""
    status = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error:
            if (
                polling
                and status == 200
                and error
                in {
                    "authorization_pending",
                    "slow_down",
                }
            ):
                return payload
            raise GitHubAuthenticationError(
                _DEVICE_ERRORS.get(error, "GitHub rejected device authorization.")
            )
    if status != 200:
        raise GitHubAuthenticationError(
            f"GitHub device authorization failed (HTTP {status}). "
            "Check GitHub availability and your network, then retry."
        )
    if payload is None:
        raise GitHubAuthenticationError(
            "GitHub device authorization returned invalid JSON. "
            "Check your network or proxy, then retry."
        )
    if not isinstance(payload, dict):
        raise GitHubAuthenticationError("Invalid GitHub device authorization response.")
    return payload


def github_user(access_token: str, *, http: Any = None) -> dict[str, Any]:
    """Verify a token with GitHub, without retaining it or exposing transport errors."""
    transport = http if http is not None else requests
    try:
        response = transport.get(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        github_user_id(payload)
        return payload
    except Exception:  # noqa: BLE001 - provider errors can contain bearer credentials.
        raise GitHubAuthenticationError(
            "GitHub identity verification failed."
        ) from None


def github_user_id(payload: dict[str, Any]) -> str:
    """Extract GitHub's stable numeric identity."""
    value = payload.get("id")
    if type(value) is int and value > 0:
        return str(value)
    raise GitHubAuthenticationError("GitHub identity verification failed.")


def authenticate_github_device(
    *,
    client_id: str,
    client_secret: str,
    on_authorization: Callable[[str, str], None],
    http: Any = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> AuthSession:
    """Authorize, verify identity, and revoke before returning a session.

    Revocation failure blocks subsequent registry writes. Cancellation after a
    token has arrived still attempts its cleanup. No broad grant is revoked.
    """
    if not client_id.strip() or not client_secret.strip():
        raise GitHubAuthenticationError(
            "GitHub OAuth client ID and secret are required."
        )
    transport = http if http is not None else requests
    token = None
    try:
        response = transport.post(
            "https://github.com/login/device/code",
            headers=_ACCEPT,
            data={"client_id": client_id},
            timeout=_TIMEOUT,
        )
        payload = _device_response(response)
        device = payload.get("device_code")
        code = payload.get("user_code")
        uri = payload.get("verification_uri")
        if uri != "https://github.com/login/device" or not all(
            isinstance(value, str) and value for value in (device, code)
        ):
            raise GitHubAuthenticationError(
                "Invalid GitHub device authorization response."
            )
        try:
            interval = float(payload.get("interval", 5))
            expires = float(payload["expires_in"])
        except (KeyError, TypeError, ValueError):
            raise GitHubAuthenticationError(
                "Invalid GitHub device authorization response."
            ) from None
        if not math.isfinite(expires) or not math.isfinite(interval) or expires <= 0:
            raise GitHubAuthenticationError(
                "Invalid GitHub device authorization response."
            )
        interval = max(1, interval)
        deadline = monotonic() + expires
        on_authorization(uri, code)
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise GitHubAuthenticationError("GitHub authorization expired.")
            sleep(min(interval, remaining))
            if monotonic() >= deadline:
                raise GitHubAuthenticationError("GitHub authorization expired.")
            response = transport.post(
                "https://github.com/login/oauth/access_token",
                headers=_ACCEPT,
                data={
                    "client_id": client_id,
                    "device_code": device,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                timeout=_TIMEOUT,
            )
            payload = _device_response(response, polling=True)
            token = payload.get("access_token")
            if isinstance(token, str) and token:
                break
            token = None
            error = payload.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            raise GitHubAuthenticationError("GitHub authorization denied or expired.")
        return AuthSession(
            github_user_id=github_user_id(github_user(token, http=transport))
        )
    except GitHubAuthenticationError:
        raise
    except requests.Timeout:
        raise GitHubAuthenticationError(
            "GitHub device authorization timed out. Check your connection and retry."
        ) from None
    except requests.exceptions.SSLError:
        raise GitHubAuthenticationError(
            "GitHub device authorization failed TLS verification. "
            "Check your trusted certificates and proxy settings."
        ) from None
    except requests.ConnectionError:
        raise GitHubAuthenticationError(
            "Could not connect to GitHub for device authorization. "
            "Check your network, DNS, and proxy settings, then retry."
        ) from None
    except Exception:  # noqa: BLE001 - redact all provider errors at the auth boundary.
        raise GitHubAuthenticationError(
            "GitHub device authentication failed."
        ) from None
    finally:
        if token:
            try:
                response = transport.delete(
                    f"https://api.github.com/applications/{client_id}/token",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    auth=(client_id, client_secret),
                    json={"access_token": token},
                    timeout=_TIMEOUT,
                )
                if response.status_code != 204:
                    raise GitHubAuthenticationError(
                        "Could not revoke the GitHub token; revocation unconfirmed."
                    )
            except Exception:  # noqa: BLE001 - never expose the revocation request token.
                raise GitHubAuthenticationError(
                    "Could not revoke the GitHub token; revocation unconfirmed."
                ) from None
            finally:
                token = None
