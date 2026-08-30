# Changelog

Curated, user-facing notes per release. Add a `## <version>` section before tagging — the release workflow puts the matching section into the GitHub Release body.

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
