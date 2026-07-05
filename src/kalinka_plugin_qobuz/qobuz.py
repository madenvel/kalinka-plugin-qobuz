import copy
import hashlib
import json
import logging
import time
from functools import partial
from typing import List, Optional

import httpx
from pydantic import BaseModel, PositiveInt

from .bundle import Bundle
from .config_model import QobuzAudioFormat, QobuzConfig

from kalinka_plugin_sdk.datamodel import (
    Album,
    Artist,
    BrowseItem,
    BrowseItemList,
    CardSize,
    Catalog,
    CatalogRole,
    CoverImage,
    EmptyList,
    EntityId,
    EntityType,
    FavoriteIds,
    Genre,
    GenreList,
    Label,
    Owner,
    Playlist,
    Preview,
    PreviewContentType,
    PreviewType,
    Track,
)
from kalinka_plugin_sdk.inputmodule import (
    InputModule,
    SearchType,
    TrackInfo,
    TrackUrl,
)

logger = logging.getLogger(__name__.split(".")[-1])


class AuthenticationError(Exception):
    pass


class IneligibleError(Exception):
    pass


class InvalidAppIdError(Exception):
    pass


class InvalidAppSecretError(Exception):
    pass


class InvalidQuality(Exception):
    pass


class NonStreamable(Exception):
    pass


# Retried: failures that are discovered in milliseconds and are genuinely
# transient. Timeouts are deliberately NOT here — a timeout has already
# consumed the full per-attempt budget, and an upstream that just hung is
# very likely to hang again, so retrying turns one slow request into
# several (3s became 7.5s worst-case). Timeouts propagate immediately.
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,          # refused / unreachable / DNS
    httpx.ReadError,             # connection reset mid-response
    httpx.RemoteProtocolError,   # server dropped a keep-alive connection
    httpx.ProxyError,
)


class RetryTransport(httpx.AsyncHTTPTransport):
    def __init__(self, read_retries=2, **kwargs):
        super().__init__(**kwargs)
        # read_retries is the total number of attempts (1 initial + N-1 retries).
        # Kept low so a request fails fast when the server has no internet —
        # otherwise the playqueue's resolution slot stays occupied far too long.
        self.read_retries = read_retries
        self.backoff_factor = 0.5

    async def handle_async_request(self, request) -> httpx.Response:
        import asyncio

        attempt = 1
        while True:
            try:
                response = await super().handle_async_request(request)
            except _RETRYABLE_EXCEPTIONS as exc:
                if attempt >= self.read_retries:
                    raise
                logger.warning("Retry %d due to %r", attempt, exc)
                await asyncio.sleep(self.backoff_factor * attempt)
                attempt += 1
                continue
            if 500 <= response.status_code < 600 and attempt < self.read_retries:
                # Release the connection before retrying; abandoning the
                # response leaks connection back-pressure under repeated 5xx.
                await response.aclose()
                logger.warning(
                    "Retry %d due to status code=%d", attempt, response.status_code
                )
                await asyncio.sleep(self.backoff_factor * attempt)
                attempt += 1
                continue
            # Final attempt's 5xx is returned to the caller, not swallowed.
            return response


# The code below is partially based on the code from
# qobuz-dl by vitiko98, fc7


def artist_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.ARTIST, source="qobuz")


def album_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.ALBUM, source="qobuz")


def track_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.TRACK, source="qobuz")


def playlist_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.PLAYLIST, source="qobuz")


def label_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.LABEL, source="qobuz")


def genre_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.GENRE, source="qobuz")


def user_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.USER, source="qobuz")


def catalog_id(id: str) -> EntityId:
    return EntityId(id=id, type=EntityType.CATALOG, source="qobuz")


class LastUpdate(BaseModel):
    favorite_tracks_ts: int = 0
    favorite_albums_ts: int = 0
    favorite_artists_ts: int = 0
    favorite_playlists_ts: int = 0


class QobuzClient:
    def __init__(self, app_id, secrets):
        logger.info(f"Logging...")
        self.secrets = secrets
        self.id = str(app_id)
        self.session = httpx.AsyncClient(
            # 2 attempts (1 initial + 1 retry), 3s per attempt. RetryTransport
            # already retries connect failures, so httpx-level retries=0 avoids
            # multiplying the worst-case wait.
            transport=RetryTransport(
                read_retries=2, retries=0, http2=True, http1=False
            ),
            # 3s read/write/pool keeps runtime calls fast-failing; connect gets a
            # longer budget so a slow-to-come-up network doesn't fail startup.
            timeout=httpx.Timeout(3.0, connect=15.0),
        )
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
                "X-App-Id": self.id,
            }
        )

        self.base = "https://www.qobuz.com/api.json/0.2/"
        self.sec = None
        # a short living cache to be used for reporting purposes
        self.track_url_response_cache = {}
        self.last_update = LastUpdate()
        self.cached = {"albums": {}, "artists": {}, "tracks": {}, "playlists": {}}

    def auth(self, user_auth_token: str):
        """Attach the pre-issued user auth token to the session.

        The token is obtained out-of-band from the Qobuz web app
        (play.qobuz.com) — users copy it from the browser devtools and paste
        it into the plugin config. All subsequent API calls ride on this
        header; a bad/expired token surfaces as 401 at the first real call.
        """
        if not user_auth_token:
            raise AuthenticationError(
                "Qobuz user auth token is not configured."
            )
        self.uat = user_auth_token
        self.session.headers.update({"X-User-Auth-Token": self.uat})

    async def load_user_info(self):
        """Resolve user_id, credential_id, and membership label from the UAT.

        Required by streaming reports (qobuz_reporter) and by playlist
        ownership filtering (playlist_user_list). Calls user/login with the
        token rather than email+password — Qobuz returns the same user object
        in both modes.
        """
        r = await self.session.get(
            self.base + "user/login",
            params={"app_id": self.id, "user_auth_token": self.uat},
        )
        if r.status_code == 401:
            raise AuthenticationError("Invalid or expired Qobuz user auth token.")
        r.raise_for_status()
        usr_info = r.json()
        if not usr_info["user"]["credential"]["parameters"]:
            raise IneligibleError("Free accounts are not eligible to play tracks.")
        self.label = usr_info["user"]["credential"]["parameters"]["short_label"]
        logger.info(f"Membership: {self.label}")
        self.credential_id = usr_info["user"]["credential"]["id"]
        self.user_id = usr_info["user"]["id"]

    async def test_secret(self, sec):
        try:
            await self.get_track_url(track_id=5966783, fmt_id=5, sec=sec)
            return True
        except InvalidAppSecretError:
            return False

    async def cfg_setup(self):
        for secret in self.secrets:
            # Falsy secrets
            if not secret:
                continue

            if await self.test_secret(secret):
                self.sec = secret
                break

        if self.sec is None:
            raise InvalidAppSecretError("Can't find any valid app secret.")

    async def get_track_url(self, track_id, fmt_id=5, sec=None):
        epoint = "track/getFileUrl"
        unix = time.time()
        if int(fmt_id) not in (5, 6, 7, 27):
            raise InvalidQuality("Invalid quality id: choose between 5, 6, 7 or 27")
        r_sig = "trackgetFileUrlformat_id{}intentstreamtrack_id{}{}{}".format(
            fmt_id, track_id, unix, self.sec if sec is None else sec
        )
        r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
        params = {
            "request_ts": unix,
            "request_sig": r_sig_hashed,
            "track_id": track_id,
            "format_id": fmt_id,
            "intent": "stream",
        }

        r = None
        for _ in range(3):
            try:
                r = await self.session.get(self.base + epoint, params=params)
                break
            except ConnectionError as e:
                logger.error(f"Connection error, retrying {_}: {e}")

        if r is None:
            raise ConnectionError("Failed to get a response after retries.")

        if r.status_code == 400:
            raise InvalidAppSecretError(f"Invalid app secret: {r.json()}.")

        r.raise_for_status()
        self.track_url_response_cache[str(track_id)] = r.json()
        return r.json()

    async def get_track_meta(self, track_id):
        epoint = "track/get"
        params = {"track_id": track_id}
        r = await self.session.get(self.base + epoint, params=params)
        if r.status_code == 400:
            raise InvalidAppSecretError(f"Invalid app secret: {r.json()}.")

        r.raise_for_status()
        return r.json()

    async def get_tracks_meta(self, track_ids: list[int]):
        epoint = "track/getList"
        params = {"tracks_id": track_ids}
        r = await self.session.post(self.base + epoint, json=params)

        if r.status_code == 400:
            raise InvalidAppSecretError(f"Invalid app secret: {r.json()}.")

        r.raise_for_status()
        return r.json()["tracks"]["items"]

    async def get_qobuz_last_update(self):
        r = await self.session.get(self.base + "user/lastUpdate")
        r.raise_for_status()

        return r.json()["last_update"]

    async def get_user_playlists(self, offset: int = 0, limit: int = 50, owner_id=None):
        # Owner filtering has to happen locally, which breaks server-side
        # pagination (a page of raw results shrinks unpredictably after
        # filtering). Fetch the full list and paginate here, exactly once.
        r = await self.session.get(
            self.base + "playlist/getUserPlaylists",
            params={"offset": 0, "limit": 500},
        )

        r.raise_for_status()

        all_playlists = r.json()["playlists"]["items"]

        if owner_id is not None:
            filtered_playlists = [
                playlist
                for playlist in all_playlists
                if playlist["owner"]["id"] == owner_id
            ]
        else:
            filtered_playlists = all_playlists

        playlists = {
            "offset": offset,
            "limit": limit,
            "total": len(filtered_playlists),
            "items": filtered_playlists[offset : offset + limit],
        }

        return {"playlists": playlists}

    async def get_user_favorites(
        self, type: SearchType, offset: int = 0, limit: int = 50
    ):
        last_update = (await self.get_qobuz_last_update())[
            {
                SearchType.album: "favorite_album",
                SearchType.artist: "favorite_artist",
                SearchType.track: "favorite_track",
            }[type]
        ]

        type_name = f"{type.name}s"

        if last_update != getattr(self.last_update, f"favorite_{type_name}_ts"):
            logger.info(f"Updating user favorites cache for {type_name}")
            r = await self.session.get(
                self.base + "favorite/getUserFavorites",
                params={"type": type.value + "s", "offset": 0, "limit": 500},
            )

            r.raise_for_status()

            self.cached[type_name] = copy.deepcopy(r.json()[type_name])

            setattr(self.last_update, f"favorite_{type_name}_ts", last_update)

        retval = {
            "offset": offset,
            "limit": limit,
            "total": len(self.cached[type_name]["items"]),
            "items": self.cached[type_name]["items"][offset : offset + limit],
        }

        return {type_name: retval}


async def get_client(config: QobuzConfig) -> QobuzClient:
    # Fetching and parsing the play.qobuz.com web bundle (a multi-megabyte
    # download from which the app id + signing secrets are scraped) is a
    # synchronous, network-bound step and the slowest part of Qobuz startup.
    # Bracket it with explicit INFO logs so the server log makes it obvious
    # when this blocking phase starts, finishes, and how long it took.
    logger.info("Loading Qobuz web bundle (app id + secrets)...")
    bundle_start = time.monotonic()
    bundle = Bundle()
    app_id = bundle.get_app_id()
    secrets = [secret for secret in bundle.get_secrets().values() if secret]
    logger.info(
        "Qobuz web bundle loaded in %.1fs (app id %s, %d secret(s))",
        time.monotonic() - bundle_start,
        app_id,
        len(secrets),
    )

    client = QobuzClient(app_id, secrets)
    client.auth(config.user_auth_token)
    await _load_user_info_resilient(client)
    await client.cfg_setup()
    return client


# A setup failure disables the plugin for the whole session, so retry the first
# authenticated call while the network is still coming up at boot.
_STARTUP_CONNECT_ATTEMPTS = 5
_STARTUP_CONNECT_BACKOFF = 2.0
_STARTUP_CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)


async def _load_user_info_resilient(client: QobuzClient) -> None:
    import asyncio

    for attempt in range(1, _STARTUP_CONNECT_ATTEMPTS + 1):
        try:
            await client.load_user_info()
            return
        except _STARTUP_CONNECT_ERRORS as exc:
            if attempt >= _STARTUP_CONNECT_ATTEMPTS:
                raise
            delay = _STARTUP_CONNECT_BACKOFF * attempt
            logger.warning(
                "Qobuz startup connect failed (attempt %d/%d): %r; retrying in %.1fs",
                attempt,
                _STARTUP_CONNECT_ATTEMPTS,
                exc,
                delay,
            )
            await asyncio.sleep(delay)


async def qobuz_link_retriever(qobuz_client, id, format_id) -> TrackUrl:
    track = await qobuz_client.get_track_url(id, fmt_id=format_id)
    track_url = TrackUrl(url=track["url"], format=track["mime_type"])
    return track_url


def append_str(s1: str, s2: str) -> str:
    if not s2:
        return s1
    else:
        return s1.strip() + f" ({s2.strip()})"


def metadata_from_track(track, album_meta={}):
    album_info = track.get("album", album_meta)
    version = album_info.get("version", None)
    return Track(
        **{
            "id": track_id(str(track["id"])),
            "title": append_str(track["title"], track.get("version", None)),
            "performer": (
                Artist(
                    name=track["performer"]["name"],
                    id=artist_id(str(track["performer"]["id"])),
                )
                if "performer" in track
                else Artist(
                    name=album_info["artist"].get("name", None),
                    id=artist_id(str(album_info["artist"].get("id", None))),
                )
            ),
            "duration": track["duration"],
            "album": Album(
                id=album_id(str(album_info["id"])),
                title=append_str(album_info["title"], version),
                image=album_info["image"],
                label=Label(
                    id=label_id(str(album_info["label"]["id"])),
                    name=album_info["label"]["name"],
                ),
                genre=Genre(
                    id=genre_id(str(album_info["genre"]["id"])),
                    name=album_info["genre"]["name"],
                ),
            ),
            "replaygain_peak": track.get("audio_info", {}).get(
                "replaygain_track_peak", None
            ),
            "replaygain_gain": track.get("audio_info", {}).get(
                "replaygain_track_gain", None
            ),
        }
    )


class QobuzInputModule(InputModule):
    def __init__(
        self,
        config: QobuzConfig,
        qobuz_client: QobuzClient,
    ):
        self.format_id = (5, 6, 7, 27)[
            list(QobuzAudioFormat).index(QobuzAudioFormat(config.format))
        ]
        logger.info(f"Selecting Format '{config.format}', id = {self.format_id}")
        self.qobuz_client = qobuz_client
        self.last_update = LastUpdate()
        self.user_playlist = []

    def module_name(self) -> str:
        return "Qobuz"

    async def search(
        self, type: SearchType, query: str, offset=0, limit=50
    ) -> BrowseItemList:
        return await self._search_items(type, query, offset, limit)

    async def browse(
        self,
        entity_id: EntityId,
        offset: PositiveInt = 0,
        limit: PositiveInt = 50,
        genre_ids: List[EntityId] = [],
    ) -> BrowseItemList:
        if entity_id.type == EntityType.ALBUM:
            return await self._browse_album(entity_id.id, offset, limit)
        elif entity_id.type == EntityType.PLAYLIST:
            return await self._browse_playlist(entity_id.id, offset, limit)
        elif entity_id.type == EntityType.ARTIST:
            return await self._browse_artist(entity_id.id, offset, limit)
        elif entity_id.type == EntityType.CATALOG:
            return await self._browse_catalog(
                entity_id.id, offset=offset, limit=limit, genre_ids=genre_ids
            )
        else:
            return EmptyList(offset, limit)

    async def _browse_album(
        self, id: str, offset: int = 0, limit: int = 50
    ) -> BrowseItemList:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "album/get",
            params={"album_id": id, "offset": offset, "limit": limit},
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        album_meta = rjson.copy()
        del album_meta["tracks"]

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["tracks"]["total"],
            items=self._tracks_to_browse_categories(
                rjson["tracks"]["items"],
                album_meta=album_meta,
            ),
        )

    async def _browse_playlist(
        self, id: str, offset: int = 0, limit: int = 50
    ) -> BrowseItemList:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "playlist/get",
            params={
                "playlist_id": id,
                "offset": offset,
                "limit": limit,
                "extra": "tracks",
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["tracks"]["total"],
            items=self._tracks_to_browse_categories(
                rjson["tracks"]["items"],
            ),
        )

    async def _browse_artist(
        self, id: str, offset: int = 0, limit: int = 50
    ) -> BrowseItemList:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "artist/get",
            params={
                "artist_id": id,
                "offset": offset,
                "limit": limit,
                "extra": "albums",
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["albums"]["total"],
            items=self._albums_to_browse_category(response.json()["albums"]["items"]),
        )

    async def list_favorite(
        self, type: SearchType, filter: str, offset: int = 0, limit: int = 50
    ) -> BrowseItemList:
        if type == SearchType.playlist:
            rjson = await self.qobuz_client.get_user_playlists(offset=0, limit=500)
        else:
            rjson = await self.qobuz_client.get_user_favorites(
                type, offset=0, limit=500
            )

        result = self._format_list_response(rjson, offset, limit)
        filtered_items = [
            item
            for item in result.items
            if (item.name and filter.lower() in item.name.lower())
            or (item.subname and filter.lower() in item.subname.lower())
        ]

        filtered_result = BrowseItemList(
            offset=offset,
            limit=limit,
            total=len(filtered_items),
            items=filtered_items[offset : offset + limit],
        )

        return filtered_result

    async def _browse_catalog(
        self,
        endpoint: str,
        offset: int = 0,
        limit: int = 50,
        genre_ids: List[EntityId] = [],
    ) -> BrowseItemList:
        if endpoint == "root":
            all_items = [
                BrowseItem(
                    id=catalog_id("recent-releases"),
                    name="Recent Releases",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("recent-releases"),
                        title="Recent Releases",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.CAROUSEL,
                            content_type=PreviewContentType.ALBUM,
                            items_count=5,
                            rows_count=1,
                            aspect_ratio=1.0,
                        ),
                        role=CatalogRole.HIDE_ON_HOME,
                    ),
                ),
                BrowseItem(
                    id=catalog_id("new-releases"),
                    name="New Releases",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("new-releases"),
                        title="New Releases",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.IMAGE_TEXT,
                            content_type=PreviewContentType.ALBUM,
                            items_count=20,
                            rows_count=2,
                            aspect_ratio=1.0,
                        ),
                        role=CatalogRole.DISCOVERY,
                    ),
                ),
                BrowseItem(
                    id=catalog_id("playlist-by-category"),
                    name="Playlist By Category",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("playlist-by-category"),
                        title="Playlist By Category",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.TEXT_ONLY,
                            content_type=PreviewContentType.CATALOG,
                            items_count=20,
                            rows_count=2,
                            aspect_ratio=1 / 0.475,
                        ),
                        role=CatalogRole.INDEX,
                    ),
                ),
                BrowseItem(
                    id=catalog_id("qobuz-playlists"),
                    name="Qobuz Playlists",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("qobuz-playlists"),
                        title="Qobuz Playlists",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.IMAGE_TEXT,
                            content_type=PreviewContentType.PLAYLIST,
                            rows_count=2,
                            items_count=20,
                            aspect_ratio=1 / 0.475,
                        ),
                        role=CatalogRole.HIDE_ON_HOME,
                    ),
                ),
                BrowseItem(
                    id=catalog_id("press-awards"),
                    name="Press Awards",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("press-awards"),
                        title="Press Awards",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.IMAGE_TEXT,
                            content_type=PreviewContentType.ALBUM,
                            items_count=14,
                            rows_count=1,
                            aspect_ratio=1.0,
                            card_size=CardSize.LARGE,
                        ),
                        role=CatalogRole.FEATURED,
                    ),
                ),
                BrowseItem(
                    id=catalog_id("most-streamed"),
                    name="Most Streamed",
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("most-streamed"),
                        title="Top Releases",
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.IMAGE_TEXT,
                            content_type=PreviewContentType.ALBUM,
                            rows_count=2,
                            aspect_ratio=1.0,
                            items_count=20,
                            card_size=CardSize.SMALL,
                        ),
                        role=CatalogRole.DISCOVERY,
                    ),
                ),
            ]
            return BrowseItemList(
                offset=offset,
                limit=limit,
                total=len(all_items),
                items=all_items[offset : offset + limit],
            )
        elif endpoint == "recent-releases":
            res = await self._get_new_releases(
                "new-releases-full", offset, max(0, min(5 - offset, limit)), genre_ids
            )
            res.total = min(res.total, 5)
            return res
        elif endpoint == "new-releases":
            return await self._get_new_releases(
                "new-releases-full", offset, limit, genre_ids
            )
        elif endpoint == "qobuz-playlists":
            return await self._get_qobuz_playlists(offset, limit, genre_ids)
        elif endpoint == "playlist-by-category":
            return await self._get_playists_by_category(offset, limit, genre_ids)
        elif endpoint == "press-awards":
            return await self._get_new_releases(
                "press-awards", offset, limit, genre_ids
            )
        elif endpoint == "most-streamed":
            return await self._get_new_releases(
                "most-streamed", offset, limit, genre_ids
            )
        else:
            ep = endpoint.split("_")
            if len(ep) > 1:
                if ep[0] == "playlist-by-category":
                    return await self._get_qobuz_playlists(
                        offset, limit, genre_ids, ep[1]
                    )
                elif ep[0] == "album-suggestions":
                    return await self._suggest_albums_similar_to(ep[1], offset, limit)
                elif ep[0] == "playlist-suggestions":
                    return await self._suggest_playlists_similar_to(
                        ep[1], offset, limit
                    )
                elif ep[0] == "similar-artists":
                    return await self._suggest_artists_similar_to(ep[1], offset, limit)

        return EmptyList(offset, limit)

    async def _get_new_releases(
        self, type: str, offset: int, limit: int, genre_ids: list[EntityId]
    ) -> BrowseItemList:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "/album/getFeatured",
            params={
                "type": type,
                "offset": offset,
                "limit": limit,
                "genre_ids": ",".join([str(genre_id.id) for genre_id in genre_ids]),
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["albums"]["total"],
            items=self._albums_to_browse_category(response.json()["albums"]["items"]),
        )

    async def _get_qobuz_playlists(
        self,
        offset: int,
        limit: int,
        genre_ids: list[EntityId],
        tags: str | None = None,
    ):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "/playlist/getFeatured",
            params={
                "type": "editor-picks",
                "offset": offset,
                "limit": limit,
                "genre_ids": ",".join([str(genre_id.id) for genre_id in genre_ids]),
                "tags": tags,
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["playlists"]["total"],
            items=self._playlists_to_browse_category(
                response.json()["playlists"]["items"]
            ),
        )

    async def _get_playists_by_category(
        self, offset: int, limit: int, genre_ids: List[EntityId]
    ):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "/playlist/getTags",
            params={
                "offset": offset,
                "limit": limit,
                "genre_ids": ",".join([str(genre_id.id) for genre_id in genre_ids]),
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        tags = response.json()["tags"]

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=len(tags),
            items=[
                BrowseItem(
                    id=catalog_id("playlist-by-category_" + tags[i]["slug"]),
                    name=json.loads(tags[i]["name_json"])["en"],
                    can_browse=True,
                    can_add=False,
                    catalog=Catalog(
                        id=catalog_id("playlist-by-category_" + tags[i]["slug"]),
                        title=json.loads(tags[i]["name_json"])["en"],
                        can_genre_filter=True,
                        preview_config=Preview(
                            type=PreviewType.IMAGE_TEXT,
                            aspect_ratio=1 / 0.475,
                        ),
                    ),
                )
                for i in range(len(tags))
            ][offset : offset + limit],
        )

    async def _get_artist_tracks(self, artist_id: str, offset: int, limit: int):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "/artist/getTracks",
            params={
                "id": artist_id,
                "offset": offset,
                "limit": limit,
            },
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["tracks"]["total"],
            items=self._tracks_to_browse_categories(response.json()["tracks"]["items"]),
        )

    async def get_track_info(self, track_ids: list[str]) -> list[TrackInfo]:
        if len(track_ids) == 0:
            return []

        all_tracks = []
        chunk_size = 49
        for i in range(0, len(track_ids), chunk_size):
            chunk = track_ids[i : i + chunk_size]
            tracks = await self.qobuz_client.get_tracks_meta([int(_) for _ in chunk])
            all_tracks.extend(tracks)
        return [self._track_to_track_info(track) for track in all_tracks]

    def _track_to_track_info(self, track):
        async def async_link_retriever():
            return await qobuz_link_retriever(
                self.qobuz_client, track["id"], self.format_id
            )

        track_info = TrackInfo(
            id=track_id(str(track["id"])),
            link_retriever=async_link_retriever,
            metadata=metadata_from_track(track),
        )

        return track_info

    def _tracks_to_browse_categories(self, tracks, album_meta={}):
        result = []
        for track in tracks:
            tid = str(track["id"])
            album = track.get("album", album_meta)
            album_version = album.get("version", None)

            browse_item = BrowseItem(
                id=track_id(tid),
                name=append_str(track["title"], track.get("version", None)),
                subname=(
                    track["performer"]["name"]
                    if "performer" in track
                    else album.get("artist", {"name": None})["name"]
                ),
                can_browse=False,
                can_add=True,
                track=Track(
                    id=track_id(tid),
                    title=append_str(track["title"], track.get("version", None)),
                    duration=track["duration"],
                    performer=(
                        Artist(
                            id=artist_id(str(track["performer"]["id"])),
                            name=track["performer"]["name"],
                        )
                        if "performer" in track
                        else None
                    ),
                    album=Album(
                        id=album_id(str(album["id"])),
                        title=append_str(album["title"], album_version),
                        artist=Artist(
                            name=album["artist"]["name"],
                            id=artist_id(str(album["artist"]["id"])),
                        ),
                        image=CoverImage(**album["image"]),
                    ),
                    playlist_track_id=str(track.get("playlist_track_id", None)),
                ),
            )
            if "favorited_at" in track:
                browse_item.timestamp = track["favorited_at"]

            result.append(browse_item)
        return result

    async def _search_items(self, item_type, query, offset, limit):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + item_type.value + "/search",
            params={"query": query, "limit": limit, "offset": offset},
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        return self._format_list_response(response.json(), offset, limit)

    def _format_list_response(self, items, offset, limit):
        if "tracks" in items:
            return BrowseItemList(
                offset=offset,
                limit=limit,
                total=items["tracks"]["total"],
                items=self._tracks_to_browse_categories(items["tracks"]["items"]),
            )

        if "albums" in items:
            return BrowseItemList(
                offset=offset,
                limit=limit,
                total=items["albums"]["total"],
                items=self._albums_to_browse_category(items["albums"]["items"]),
            )

        if "playlists" in items:
            return BrowseItemList(
                offset=offset,
                limit=limit,
                total=items["playlists"]["total"],
                items=self._playlists_to_browse_category(items["playlists"]["items"]),
            )

        if "artists" in items:
            return BrowseItemList(
                offset=offset,
                limit=limit,
                total=items["artists"]["total"],
                items=self._artists_to_browse_category(items["artists"]["items"]),
            )

        return EmptyList(offset, limit)

    def _artists_to_browse_category(self, artists):
        return [
            BrowseItem(
                id=artist_id(str(artist["id"])),
                name=artist["name"],
                subname=None,
                can_browse=True,
                can_add=False,
                timestamp=artist.get("favorited_at", 0),
                artist=Artist(
                    id=artist_id(str(artist["id"])),
                    name=artist["name"],
                    image=(
                        CoverImage(
                            thumbnail=artist["image"].get("small", None),
                            small=artist["image"].get("medium", None),
                            large=artist["image"].get("large", None),
                        )
                        if artist["image"]
                        else None
                    ),
                    album_count=artist["albums_count"],
                ),
                sections=[
                    BrowseItem(
                        id=artist_id(str(artist["id"])),
                        name="Albums",
                        can_browse=True,
                        can_add=False,
                        catalog=Catalog(
                            id=artist_id(str(artist["id"])),
                            title="Albums",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.TILE,
                                content_type=PreviewContentType.ALBUM,
                                items_count=10,
                                rows_count=1,
                                aspect_ratio=1.0,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                    BrowseItem(
                        id=catalog_id("similar-artists_" + str(artist["id"])),
                        name="Similar artists",
                        can_browse=True,
                        can_add=False,
                        catalog=Catalog(
                            id=catalog_id("similar-artists_" + str(artist["id"])),
                            title="Similar artists",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.IMAGE_TEXT,
                                content_type=PreviewContentType.ARTIST,
                                items_count=5,
                                rows_count=1,
                                aspect_ratio=1.0,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                ],
            )
            for artist in artists
        ]

    def _albums_to_browse_category(self, albums):
        return [
            BrowseItem(
                id=album_id(str(album["id"])),
                name=append_str(album["title"], album.get("version", None)),
                subname=(
                    (artist := self._extract_artist_from_album(album)) and artist.name
                ),
                can_browse=True,
                can_add=True,
                timestamp=album.get("favorited_at", 0),
                album=Album(
                    id=album_id(str(album["id"])),
                    title=append_str(album["title"], album.get("version", None)),
                    artist=artist,
                    image=(
                        CoverImage(
                            thumbnail=album["image"].get("thumbnail", None),
                            small=album["image"].get("small", None),
                            large=album["image"].get("large", None),
                        )
                        if "image" in album and album["image"]
                        else None
                    ),
                    duration=album["duration"],
                    track_count=album.get("track_count", album.get("tracks_count", 0)),
                    genre=Genre(
                        id=genre_id(str(album["genre"]["id"])),
                        name=album["genre"]["name"],
                    ),
                ),
                sections=[
                    BrowseItem(
                        id=album_id(str(album["id"])),
                        name="Tracks",
                        can_browse=True,
                        can_add=True,
                        catalog=Catalog(
                            id=album_id(str(album["id"])),
                            title="Tracks",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.TILE_NUMBERED,
                                content_type=PreviewContentType.TRACK,
                                items_count=10,
                                rows_count=1,
                                aspect_ratio=1.0,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                    *(
                        [
                            BrowseItem(
                                id=artist.id,
                                name="More from this artist",
                                can_browse=True,
                                can_add=False,
                                catalog=Catalog(
                                    id=artist.id,
                                    title="More from this artist",
                                    can_genre_filter=False,
                                    preview_config=Preview(
                                        type=PreviewType.IMAGE_TEXT,
                                        content_type=PreviewContentType.ALBUM,
                                        items_count=10,
                                        rows_count=1,
                                        aspect_ratio=1.0,
                                        card_size=CardSize.SMALL,
                                    ),
                                ),
                            )
                        ]
                        if artist
                        else []
                    ),
                    BrowseItem(
                        id=catalog_id("album-suggestions_" + str(album["id"])),
                        name="You may also like",
                        can_browse=True,
                        can_add=False,
                        catalog=Catalog(
                            id=catalog_id("album-suggestions_" + str(album["id"])),
                            title="You may also like",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.IMAGE_TEXT,
                                content_type=PreviewContentType.ALBUM,
                                items_count=5,
                                rows_count=1,
                                aspect_ratio=1.0,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                ],
            )
            for album in albums
        ]

    def _extract_artist_from_album(self, album) -> Optional[Artist]:
        if "artist" in album:
            return Artist(
                id=artist_id(str(album["artist"]["id"])),
                name=album["artist"]["name"],
            )
        elif "performer" in album:
            return Artist(
                id=artist_id(str(album["performer"]["id"])),
                name=album["performer"]["name"],
            )
        elif "artists" in album:
            return Artist(
                id=artist_id(str(album["artists"][0]["id"])),
                name=album["artists"][0]["name"],
            )
        else:
            return None

    def _playlists_to_browse_category(self, playlists):
        return [
            BrowseItem(
                id=playlist_id(str(playlist["id"])),
                name=playlist["name"],
                subname=playlist["owner"]["name"],
                can_browse=True,
                can_add=True,
                playlist=self._qobuz_playlist_to_playlist(playlist),
                sections=[
                    BrowseItem(
                        id=playlist_id(str(playlist["id"])),
                        name="Tracks",
                        can_browse=True,
                        can_add=True,
                        catalog=Catalog(
                            id=playlist_id(str(playlist["id"])),
                            title="Tracks",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.TILE,
                                content_type=PreviewContentType.TRACK,
                                items_count=15,
                                rows_count=1,
                                aspect_ratio=1.0,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                    BrowseItem(
                        id=catalog_id("playlist-suggestions_" + str(playlist["id"])),
                        name="Similar playlists",
                        can_browse=True,
                        can_add=False,
                        catalog=Catalog(
                            id=catalog_id(
                                "playlist-suggestions_" + str(playlist["id"])
                            ),
                            title="Similar playlists",
                            can_genre_filter=False,
                            preview_config=Preview(
                                type=PreviewType.IMAGE_TEXT,
                                content_type=PreviewContentType.PLAYLIST,
                                items_count=9,
                                rows_count=1,
                                aspect_ratio=1 / 0.475,
                                card_size=CardSize.SMALL,
                            ),
                        ),
                    ),
                ],
            )
            for playlist in playlists
        ]

    def _qobuz_playlist_to_playlist(self, playlist):
        images = playlist.get("images", [None])
        images150 = playlist.get("images150", [None])
        images300 = playlist.get("images300", [None])
        image_rectangle = playlist.get("image_rectangle", images300)
        image_rectangle_mini = playlist.get("image_rectangle_mini", images)

        return Playlist(
            id=playlist_id(str(playlist["id"])),
            name=playlist["name"],
            owner=Owner(
                name=playlist["owner"]["name"],
                id=user_id(str(playlist["owner"]["id"])),
            ),
            image=CoverImage(
                small=images150[0] if images150 else None,
                large=image_rectangle[0] if image_rectangle else None,
                thumbnail=image_rectangle_mini[0] if image_rectangle_mini else None,
            ),
            description=playlist["description"],
            track_count=playlist["tracks_count"],
        )

    async def get_favorite_ids(self) -> FavoriteIds:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "favorite/getUserFavoriteIds",
            params={"limit": 5000},
        )

        if response.is_success != True:
            return FavoriteIds()

        rjson = response.json()

        return FavoriteIds(
            albums=[album_id(str(id)) for id in rjson["albums"]],
            artists=[artist_id(str(id)) for id in rjson["artists"]],
            tracks=[track_id(str(id)) for id in rjson["tracks"]],
            playlists=await self._get_favorite_playlist_ids(),
        )

    async def _get_favorite_playlist_ids(self) -> list[EntityId]:
        rjson = await self.qobuz_client.get_user_playlists(limit=500)

        return [
            playlist_id(str(playlist["id"])) for playlist in rjson["playlists"]["items"]
        ]

    async def add_to_favorite(self, id: str):
        entity_id = EntityId.from_string(id)

        if entity_id.type == EntityType.PLAYLIST:
            endpoint = "playlist/subscribe"
            params = {"playlist_id": entity_id.id}
        else:
            endpoint = "favorite/create"
            params = {entity_id.type.value + "_ids": entity_id.id}

        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + endpoint, params=params
        )

        response.raise_for_status()

        rjson = response.json()

        logger.info(f"Add to favorite response: {rjson}")

        if "status" not in rjson or rjson["status"] != "success":
            raise Exception(f"Failed to add to favorite: {response.text}")

    async def remove_from_favorite(self, id: str):
        entity_id = EntityId.from_string(id)

        if entity_id.type == EntityType.PLAYLIST:
            endpoint = "playlist/unsubscribe"
            params = {"playlist_id": entity_id.id}
        else:
            endpoint = "favorite/delete"
            params = {entity_id.type.value + "_ids": entity_id.id}

        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + endpoint, params=params
        )

        response.raise_for_status()

        rjson = response.json()

        if "status" not in rjson or rjson["status"] != "success":
            raise Exception(f"Failed to remove from favorite: {response.text}")

    async def list_genre(self, offset: int, limit: int) -> GenreList:
        endpoint = "genre/list"
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + endpoint
        )

        response.raise_for_status()

        rjson = response.json()

        return GenreList(
            offset=offset,
            limit=limit,
            total=rjson["genres"]["total"],
            items=[
                Genre(
                    id=genre_id(str(genre["id"])),
                    name=genre["name"],
                )
                for genre in rjson["genres"]["items"]
            ],
        )

    async def get(self, entity_id: EntityId) -> BrowseItem:
        if entity_id.type == EntityType.ALBUM:
            return await self._album_get(entity_id.id)
        elif entity_id.type == EntityType.PLAYLIST:
            return await self._playlist_get(entity_id.id)
        elif entity_id.type == EntityType.ARTIST:
            return await self._artist_get(entity_id.id)
        elif entity_id.type == EntityType.TRACK:
            return await self._track_get(entity_id.id)
        else:
            raise ValueError(f"Unsupported EntityId type: {entity_id.type.name}")

    async def _album_get(self, id: str) -> BrowseItem:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "album/get",
            params={"album_id": id, "offset": 0, "limit": 0},
        )

        response.raise_for_status()

        rjson = response.json()

        return self._albums_to_browse_category([rjson])[0]

    async def _playlist_get(self, id: str) -> BrowseItem:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "playlist/get",
            params={
                "playlist_id": id,
                "offset": 0,
                "limit": 0,
            },
        )

        response.raise_for_status()

        rjson = response.json()

        return self._playlists_to_browse_category([rjson])[0]

    async def _artist_get(self, id: str) -> BrowseItem:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "artist/get",
            params={
                "artist_id": id,
            },
        )

        response.raise_for_status()

        rjson = response.json()

        return self._artists_to_browse_category([rjson])[0]

    async def _track_get(self, id: str) -> BrowseItem:
        rjson = await self.qobuz_client.get_track_meta(id)
        return self._tracks_to_browse_categories([rjson])[0]

    def _to_playlist_response(self, obj):
        return Playlist(
            id=playlist_id(str(obj["id"])),
            name=obj["name"],
            description=obj["description"],
            track_count=obj["tracks_count"],
            owner=Owner(
                name=obj["owner"]["name"],
                id=user_id(str(obj["owner"]["id"])),
            ),
        )

    async def playlist_user_list(
        self, offset: int = 0, limit: int = 25
    ) -> BrowseItemList:
        rjson = await self.qobuz_client.get_user_playlists(
            offset=offset, limit=limit, owner_id=self.qobuz_client.user_id
        )

        return self._format_list_response(rjson, offset, limit)

    async def playlist_create(self, name, description) -> Playlist:
        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + "playlist/create",
            params={"name": name, "description": description},
        )

        response.raise_for_status()

        rjson = response.json()

        return self._to_playlist_response(rjson)

    async def playlist_update(self, id, name, description) -> Playlist:
        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + "playlist/update",
            params={
                "playlist_id": EntityId.from_string(id).id,
                "name": name,
                "description": description,
            },
        )

        response.raise_for_status()

        rjson = response.json()

        return self._to_playlist_response(rjson)

    async def playlist_delete(self, id):
        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + "playlist/delete",
            params={"playlist_id": EntityId.from_string(id).id},
        )

        response.raise_for_status()

        return response.json()

    async def playlist_add_tracks(
        self, id: str, track_ids: List[str], allow_duplicates: bool
    ) -> Playlist:
        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + "playlist/addTracks",
            params={
                "no_duplicate": not allow_duplicates,
                "playlist_id": EntityId.from_string(id).id,
                "track_ids": ",".join(
                    (EntityId.from_string(track_id).id for track_id in track_ids)
                ),
            },
        )

        response.raise_for_status()
        rjson = response.json()

        return self._to_playlist_response(rjson)

    async def playlist_remove_tracks(self, id, playlist_track_ids):
        response = await self.qobuz_client.session.post(
            self.qobuz_client.base + "playlist/deleteTracks",
            params={
                "playlist_id": EntityId.from_string(id).id,
                "playlist_track_ids": ",".join(playlist_track_ids),
            },
        )

        response.raise_for_status()
        rjson = response.json()

        return self._to_playlist_response(rjson)

    async def _suggest_albums_similar_to(
        self, id: str, offset: int = 0, limit: int = 25
    ) -> BrowseItemList:
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "album/suggest",
            params={"album_id": id},
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()
        albums = rjson["albums"]["items"][offset : offset + limit]

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=int(rjson["albums"]["limit"]),
            items=self._albums_to_browse_category(albums),
        )

    async def _suggest_playlists_similar_to(
        self, id: str, offset: int, limit: int = 10
    ):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "playlist/get",
            params={"playlist_id": id, "extra": "getSimilarPlaylists"},
        )

        if response.is_success != True:
            return EmptyList(offset, limit)

        rjson = response.json()
        playlists = rjson["similarPlaylist"]["items"][offset : offset + limit]

        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=len(rjson["similarPlaylist"]["items"]),
            items=self._playlists_to_browse_category(playlists),
        )

    async def _suggest_artists_similar_to(self, id: str, offset: int, limit: int = 10):
        response = await self.qobuz_client.session.get(
            self.qobuz_client.base + "artist/getSimilarArtists",
            params={"artist_id": id, "offset": offset, "limit": limit},
        )
        if response.is_success != True:
            return EmptyList(offset, limit)
        rjson = response.json()
        artists = rjson["artists"]["items"]
        return BrowseItemList(
            offset=offset,
            limit=limit,
            total=rjson["artists"]["total"],
            items=self._artists_to_browse_category(artists),
        )

    async def get_resource_path(self, id) -> str | None:
        return None
