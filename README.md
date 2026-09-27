# Qobuz Plugin for Kalinka Music Player

## Overview

This plugin was generated from the Kalinka Plugin cookiecutter template and provides a input_module implementation for the Kalinka Music Player system.

This is an experimental integration with [Qobuz](https://www.qobuz.com), allowing you to mix local tracks and Qobuz items inside the same play queue. Qobuz support is minimal and may change at any time.

**For using the plugin you must have a valid Qobuz subscription**

>**Disclaimer**: This plugin is an independent, community-developed integration and is not affiliated with, endorsed by, or supported by Qobuz or its parent companies. It is provided "as is", without any guarantees or warranties of any kind. Use of this plugin is entirely at your own risk. The author assumes no responsibility or liability for any consequences, including but not limited to potential violations of Qobuz's Terms of Service or any other issues arising from its use.

## Building

### Prerequisites
- Python 3.10+
- `kalinka-plugin-sdk` package
- Build tools: `python3-build`, `setuptools`, `setuptools-scm`, `wheel`
- For Debian packaging: `dpkg-dev`
- Git repository with proper tags for version detection

### Version Management
This plugin uses **setuptools_scm** for automatic version detection:
- **Release builds**: Tag your release with `kalinka-plugin-kalinka-plugin-qobuz-v1.2.3` format
- **Development builds**: setuptools_scm automatically generates dev versions like `1.2.4.dev0+gc1e6070.d20250928`
- **Clean releases**: Commit all changes and tag for clean release versions

### Build Python Wheel
```bash
./scripts/build_wheel.sh
```
The script automatically:
- Detects version from git tags using setuptools_scm
- Generates `_version.py` with the detected version
- Builds the wheel with proper version metadata

### Build Debian Package
```bash
./scripts/build_deb.sh
```
The script automatically:
- Builds the wheel first to detect the version
- Generates Debian control files with the correct version
- Creates a `.deb` package ready for installation

The Debian package will:
1. Install the wheel to `/usr/share/kalinka/plugins/`
2. Use post-install script to install into Kalinka's venv
3. Restart Kalinka service if available

## Installation

### From Wheel
```bash
# Install into Kalinka's venv
/opt/kalinka/venv/bin/pip install kalinka-plugin-kalinka-plugin-qobuz-*.whl
```

### From Debian Package
```bash
sudo dpkg -i kalinka-plugin-kalinka-plugin-qobuz_*_all.deb
```

## Linking your Qobuz account

The plugin links to your account through the official Qobuz app. There is no token to copy.

1. Enable Qobuz in Kalinka's settings. While it is not linked, the player advertises itself on your network as **Kalinka (hostname)**. You can change that name under *Qobuz Connect device name*.
2. On a phone or computer on the same network, open the Qobuz app and open its device picker, where you would choose a speaker.
3. Choose Kalinka. The app hands the player a token that lasts an hour. The plugin exchanges it for a regular Qobuz user auth token, the same kind the old *User auth token* setting held, and checks it: it reads your account, favourites, playlists, new releases and a stream URL.
4. The *Qobuz account* line in Qobuz's settings then reads **Linked**. Kalinka stops advertising, and you browse and play Qobuz in Kalinka as before.

In the Qobuz app, Kalinka shows a spinner for a while, then the app switches to another device. That is expected: the plugin uses Qobuz Connect only to receive the token and never joins the app's playback session. Kalinka's status line tells you whether linking worked; reopen its settings to see it.

### What the status line means

| Status | Meaning |
|---|---|
| Starting | Loading the Qobuz web player's app details; waits for the network if needed. |
| Not linked | Waiting for you to choose this player in the Qobuz app. A failed attempt says why. |
| Pairing | Checking the account the app handed over. |
| Linked | Qobuz works. If Qobuz issued no user auth token, the app's one-hour token renews itself before it expires. |
| Reconnecting | After a restart, checking the stored link; retries while Qobuz is unreachable. |
| Link expired | Qobuz refused the stored link or its renewal. Unpair, then pair again. |
| Pairing unavailable | The pairing port is taken or there is no network address; retried every 30 seconds. |

The status is read when the settings page opens, so reopen it to see a change.

Until an account is linked, Qobuz reports itself as unavailable (an error badge in the module list) and lists nothing: no shelves, search results, favourites or playlists. Starting and reconnecting with a stored link show as a warning instead, since the link is on its way.

### Unpairing

A linked player refuses every other pairing attempt, from any phone, until you unpair it. This also holds after a restart or when the link has expired. To link another account:

1. Turn on **Unpair Qobuz account on next restart** and apply. Kalinka restarts.
2. The plugin forgets the account and its tokens, and the switch turns itself off.
3. The player advertises again. Choose it in the Qobuz app.

### Network

Pairing needs mDNS (UDP 5353) and one TCP port, 8183 by default (*Qobuz Connect pairing port*), reachable from the phone over IPv4 on the same LAN. Neither is used once the account is linked.

The linked token is kept in `/var/lib/kalinka/qobuz/connect.json`, readable only by the Kalinka service user.

### Upgrading from 4.x or older

The *User auth token* setting is gone. A token saved by an older version is ignored, and the server logs one warning about it on each start. To silence it, delete the `input_modules.qobuz.user_auth_token` entry from `/etc/kalinka/kalinka_conf.cfg`.

### Limitations

- This is a prototype. The pairing protocol is not documented by Qobuz and was learnt from other receivers.
- User auth tokens have lasted months in practice. If Qobuz does not issue one, the plugin keeps the app's one-hour token and renews it every hour, which has not been proven over days.
- Kalinka is not a Qobuz Connect speaker. Playback commands from the Qobuz app are not accepted.

## Live smoke test

Run this on a real player with a Qobuz subscription before releasing. Use throwaway favourites and playlists for the steps that change your account.

1. Install the build (`./scripts/build_deb.sh`, then `sudo apt install ./kalinka-plugin-qobuz_*_all.deb`). Check the player is advertised and answers:
   ```sh
   avahi-browse -rt _qobuz-connect._tcp
   curl http://<player-ip>:8183/streamcore/get-display-info
   ```
2. Choose the player in the Qobuz app. Follow the server log (`journalctl -u kalinka -f`). Note the handoff's key names and claim names, which account endpoint answered, and each check. The "Qobuz account linked" line names the credential kept: `user_auth_token`, or `bearer` if Qobuz issued none.
3. In Kalinka, confirm the status reads **Linked**. Then:
   - browse Qobuz, your favourites and your playlists;
   - add and remove a favourite, and create and delete a playlist;
   - play a Qobuz track, then a local track in the same queue;
   - confirm `reportStreamingStart` and `reportStreamingEnd` succeed in the log.
4. Send a second handoff, from another phone or with `curl -X POST` and any body. It must be refused with HTTP 400, and the status must not change.
5. Confirm playback still works after `sudo systemctl restart kalinka`, and again the next day. If the link kept a `bearer` credential, also wait past the first renewal; the log shows the expiry before and after.
6. Turn on Unpair and apply. Confirm the player is advertised again and that pairing works a second time.

## Development

### Testing
Run the included smoke tests:

```bash
pytest tests/
```

## License

This plugin is released under the [Apache License 2.0](LICENSE).

## Support

For questions about this plugin or plugin development in general:
- Check the Kalinka Plugin SDK documentation
- Review other plugins in the ecosystem
- Consult the main Kalinka project documentation
