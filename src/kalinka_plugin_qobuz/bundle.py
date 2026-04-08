# The code below is based on qobuz-dl package
# Authored by vitiko98, modified by qwerzl

import base64
import logging
import re
from collections import OrderedDict

import httpx

# Modified code based on DashLt's spoofbuz

logger = logging.getLogger(__name__)

_SEED_TIMEZONE_REGEX = re.compile(
    r'[a-z]\.initialSeed\("(?P<seed>[\w=]+)",window\.utimezone\.(?P<timezone>[a-z]+)\)'
)
_INFO_EXTRAS_REGEX = r'name:"\w+/(?P<timezone>{timezones})",info:"(?P<info>[\w=]+)",extras:"(?P<extras>[\w=]+)"'
_APP_ID_REGEX = re.compile(
    r'production:{api:{appId:"(?P<app_id>\d{9})"'
)
_APP_SECRET_FALLBACK_REGEX = re.compile(
    r'appSecret:"(?P<secret>[0-9a-f]{32})"'
)
_PRIVATE_KEY_REGEX = re.compile(r'privateKey:"(?P<private_key>[^"]+)"')

_BASE_URL = "https://play.qobuz.com"
_BUNDLE_URL_REGEX = re.compile(
    r'<script src="(/resources/[\w.\-]+/bundle\.js)"></script>'
)


class Bundle:
    def __init__(self):
        self._session = httpx.Client(http2=True, timeout=5)

        logger.debug("Getting logging page")
        response = self._session.get(f"{_BASE_URL}/login")
        response.raise_for_status()

        bundle_url_match = _BUNDLE_URL_REGEX.search(response.text)
        if not bundle_url_match:
            raise NotImplementedError("Bundle URL not found")

        bundle_url = bundle_url_match.group(1)

        logger.debug("Getting bundle")
        response = self._session.get(_BASE_URL + bundle_url)
        response.raise_for_status()

        self._bundle = response.text
        self._session.close()

    def get_private_key(self):
        match = _PRIVATE_KEY_REGEX.search(self._bundle)
        return match.group("private_key") if match else None

    def get_app_id(self):
        match = _APP_ID_REGEX.search(self._bundle)
        if not match:
            raise NotImplementedError("Failed to match APP ID")

        return match.group("app_id")

    def get_secrets(self):
        logger.debug("Getting secrets")
        seed_matches = _SEED_TIMEZONE_REGEX.finditer(self._bundle)
        secrets = OrderedDict()

        for match in seed_matches:
            seed, timezone = match.group("seed", "timezone")
            secrets[timezone] = [seed]

        keypairs = list(secrets.items())
        if len(keypairs) >= 2:
            secrets.move_to_end(keypairs[1][0], last=False)

        if secrets:
            info_extras_regex = _INFO_EXTRAS_REGEX.format(
                timezones="|".join([timezone.capitalize() for timezone in secrets])
            )
            info_extras_matches = re.finditer(info_extras_regex, self._bundle)
            for match in info_extras_matches:
                timezone, info, extras = match.group("timezone", "info", "extras")
                secrets[timezone.lower()] += [info, extras]
            for secret_pair in secrets:
                secrets[secret_pair] = base64.standard_b64decode(
                    "".join(secrets[secret_pair])[:-44]
                ).decode("utf-8")

        if not any(secrets.values()):
            logger.warning("Primary secret extraction failed, trying fallback")
            fallback_secrets = OrderedDict()
            for i, match in enumerate(_APP_SECRET_FALLBACK_REGEX.finditer(self._bundle)):
                fallback_secrets[f"fallback_{i}"] = match.group("secret")
            return fallback_secrets

        return secrets
