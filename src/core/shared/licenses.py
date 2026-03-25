"""License normalization helpers shared by adapter and dataset builders."""

from __future__ import annotations


_SPDX_TO_URL = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-NC-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-ND-4.0": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "MIT": "https://opensource.org/licenses/MIT",
    "APACHE-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
    "GPL-3.0": "https://www.gnu.org/licenses/gpl-3.0.html",
    "BSD-3-CLAUSE": "https://opensource.org/licenses/BSD-3-Clause",
}


def normalize_license_url(value: str) -> str:
    """Return a canonical license URL when a known SPDX token is provided.

    Args:
        value: A license URL or SPDX-like short name.

    Returns:
        The original URL or a mapped canonical license URL.
    """
    if value.startswith(("http://", "https://")):
        return value
    return _SPDX_TO_URL.get(value.upper(), value)
