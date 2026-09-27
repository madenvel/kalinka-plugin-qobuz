# Changelog

Curated, user-facing notes per release. Add a `## <version>` section before tagging — the release workflow puts the matching section into the GitHub Release body.

## 5.0.0

### Changed
- **Link Qobuz from the Qobuz app instead of pasting a token.** While Qobuz is not linked, the player shows up in the Qobuz app's device picker. Choosing it there hands the player a token, which the plugin exchanges for a regular Qobuz user auth token and checks against your account, favourites, playlists, the catalogue and a stream before using it. Browsing, search, favourites, playlists, playback quality and streaming reports work as before. The Qobuz app shows a spinner and then moves to another device; that is expected, and Kalinka's settings say whether the link worked.
- **The *User auth token* setting is gone.** A token saved by an older version is ignored; the server logs one warning about it on each start until the entry is removed from `/etc/kalinka/kalinka_conf.cfg`. Link again from the Qobuz app after upgrading.
- Qobuz now starts without waiting for the network, so a player that boots before its network still shows Qobuz and how to link it.
- Until an account is linked, Qobuz is marked unavailable and lists nothing: no shelves, search results, favourites or playlists. It never empties favourites, playlists or search results from other sources.
- Qobuz's startup checks no longer rely on one fixed test track, which can disappear from the catalogue or a region; they use a track from current new releases.

### Added
- A *Qobuz account* status line in Qobuz's settings: not linked, pairing, linked (with the account), reconnecting, or expired.
- **Unpair Qobuz account on next restart**, to forget the linked account and pair another. A linked player refuses every other pairing until it is unpaired, across restarts and expiry.
- If Qobuz issues no user auth token, the app's one-hour token is kept and renews itself before it expires.
- Expert settings for the name shown in the Qobuz app and for the pairing port.

This is a prototype: the pairing protocol is undocumented, and the hourly renewal fallback has not yet run against a real account for days.

## 3.0.0

### Changed
- **Requires Kalinka plugin SDK 2.0 or newer, and a server built against it.** The SDK changed how a track says where its audio comes from, and this release follows that change. It will not load on an older server, and an older Qobuz plugin will not load on a new one — upgrade the server and the plugin together.

Playback itself is unchanged: Qobuz still signs a URL per play and your renderer still fetches the audio straight from Qobuz, not through the Kalinka server.

## 2.3.0

### Changed
- The web bundle download during Qobuz startup no longer blocks the server's event loop, so everything else stays responsive while Qobuz starts.
- That download now runs under a two-minute deadline: a network black hole (such as a DNS server that never answers) fails Qobuz startup with a clear error instead of stalling it indefinitely.

Nothing about playback, authentication or catalogue browsing changed in this release.

## 2.2.0

### Added
- Qobuz can now be set up from the app's first-run wizard. The plugin marks its **User auth token** as required and its **Audio quality** as worth asking, so the wizard knows what to ask for and what it can leave alone.
- Qobuz now describes itself — "Streaming from a Qobuz subscription, up to studio-quality hi-res. Needs your Qobuz account token." — so the app can explain the source while you are deciding whether to enable it, before it is configured.

### Changed
- Relicensed from GPL-3.0-or-later to the Apache License 2.0.

Needs a server and app new enough to read the setup information; older ones ignore it and behave as before. Nothing about playback, authentication or catalogue browsing changed in this release.

## 2.1.0

### Added
- Sections on the Qobuz root page now carry a short subname, so it is clearer what each row of the catalogue is.

### Changed
- Playlists browsed by category are shown as text tiles instead of image cards.
- Qobuz gets more time to start up on slow networks.
- HTTP requests fail fast (3 second timeout, one retry) instead of hanging, and timeouts are no longer retried.
- The web bundle load is logged with start and finish timing, and retry logs are no longer blank.

## 2.0.0

### Changed
- The Qobuz API client is now asynchronous, authentication uses a user auth token, and the packaging was reworked.

## 1.0.0

First release.
