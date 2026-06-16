"""On-disk cache for the Qobuz web-bundle credentials.

Qobuz does not publish a stable app id / signing secret; the values are
scraped out of the play.qobuz.com web-player bundle (see :mod:`bundle`).
Fetching and regex-parsing that bundle is a multi-second, multi-megabyte
network operation that ``get_client`` otherwise runs on *every* startup,
which dominates the server's "time to accept connections".

The credentials change very rarely, so we persist the validated app id +
secret and reuse them on the next start, only re-fetching the bundle on a
cache miss or when the API later rejects the cached values. This keeps the
existing init contract intact — the client is still fully initialised before
it is handed out — it just skips the slow download on the common path.

What is cached here are Qobuz's *public* web-app credentials (identical for
every user, served to any anonymous visitor of play.qobuz.com); the user's
own ``user_auth_token`` is never written here.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Bump when the on-disk shape changes so stale-format files are ignored
# rather than mis-read.
_CACHE_VERSION = 1
_CACHE_FILENAME = "qobuz_bundle.json"


def _cache_dir() -> Path:
    """Directory for the bundle cache, for a headless service account.

    The server runs as a system user (``kalusr``) with **no home directory**,
    so anything derived from ``~`` is wrong — ``expanduser('~')`` would leave a
    literal ``~`` and create a bogus dir under the process CWD. Resolve in
    order:

    1. ``$CACHE_DIRECTORY`` — exported by systemd from ``CacheDirectory=kalinka``
       (``/var/cache/kalinka``, owned by and writable for the service user).
       systemd may hand back a ``:``-separated list; the first entry is ours.
    2. ``$XDG_CACHE_HOME/kalinka`` — for non-systemd / dev runs that opt in.
    3. ``/var/cache/kalinka`` — the packaged default location.
    """
    cache_directory = os.environ.get("CACHE_DIRECTORY")
    if cache_directory:
        return Path(cache_directory.split(":")[0])
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "kalinka"
    return Path("/var/cache/kalinka")


def _cache_path() -> Path:
    """Location of the bundle cache file."""
    return _cache_dir() / _CACHE_FILENAME


def load_cached_bundle() -> Optional[Tuple[str, str]]:
    """Return the cached ``(app_id, secret)`` pair, or ``None`` if there is no
    usable cache (missing, unreadable, wrong version, or malformed)."""
    path = _cache_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        logger.warning("Ignoring unreadable Qobuz bundle cache %s: %s", path, e)
        return None

    if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
        return None
    app_id = data.get("app_id")
    secret = data.get("secret")
    if not app_id or not secret:
        return None
    return str(app_id), str(secret)


def save_cached_bundle(app_id: str, secret: str) -> None:
    """Persist the validated ``app_id`` + ``secret``. Best-effort: a failure to
    write only costs a bundle re-fetch next time, so it is logged, not raised."""
    if not app_id or not secret:
        return
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash mid-write can't leave a half file that
        # later reads as malformed.
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(
                {"version": _CACHE_VERSION, "app_id": app_id, "secret": secret}, fh
            )
        tmp.replace(path)
    except OSError as e:
        logger.warning("Could not write Qobuz bundle cache %s: %s", path, e)


def clear_cached_bundle() -> None:
    """Remove the cache file (e.g. after the API rejected the cached values)."""
    try:
        _cache_path().unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Could not remove Qobuz bundle cache: %s", e)
