from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


class FetchError(Exception):
    """A source could not be fetched. Reported in the digest's source health."""


def fetch(url: str, params: dict | None = None, accept: str = "*/*") -> bytes:
    """GET a URL with an honest user agent, a timeout and bounded retries.

    4xx responses fail immediately: they are blocks or bad addresses, not outages, and
    are never retried or worked around.
    """
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": config.USER_AGENT, "Accept": accept}
    )
    last_error: Exception | None = None
    for attempt in range(config.HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if err.code == 429 or err.code >= 500:
                last_error = err
            else:
                raise FetchError(f"HTTP {err.code} for {url}") from err
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last_error = err
        if attempt < config.HTTP_RETRIES:
            time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"gave up after {config.HTTP_RETRIES + 1} attempts: {last_error} ({url})")
