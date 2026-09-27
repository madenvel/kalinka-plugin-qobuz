#!/usr/bin/env bash
#
# install-latest.sh — install or upgrade the Qobuz plugin from its latest
# GitHub release.
#
# The plugin is one arch-independent (_all) .deb, so this works on any machine
# the Kalinka server was installed on with its .deb packages: a Raspberry Pi,
# any other Debian or Ubuntu box, or a virtual machine. The .deb is checked
# against the release's SHA256SUMS and installed with apt; the server restarts
# by itself to load it. Run it again at any time to upgrade.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/madenvel/kalinka-plugin-qobuz/main/scripts/install-latest.sh | sudo bash
#
# Env, passed after sudo, which drops the caller's own:
#   curl -fsSL <url> | sudo GITHUB_TOKEN=... bash
#
#   KALINKA_QOBUZ_REPO  owner/repo to install from (default: madenvel/kalinka-plugin-qobuz)
#   GITHUB_TOKEN        optional, only to avoid the 60-req/hr anonymous API limit
#
# Everything runs inside main(), called on the last line, so a download cut
# short when piped into bash runs nothing at all.
set -euo pipefail

PACKAGE="kalinka-plugin-qobuz"
TMP=""

have() { command -v "$1" >/dev/null 2>&1; }

die() { echo "error: $*" >&2; exit 1; }

cleanup() { if [ -n "$TMP" ]; then rm -rf "$TMP"; fi; }
trap cleanup EXIT

api() {  # api <url>: a GitHub API GET, with the token when there is one
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    # Read from a file descriptor, so the token stays out of the process list.
    curl -fsSL -H @<(printf 'Authorization: Bearer %s\n' "$GITHUB_TOKEN") "$1"
  else
    curl -fsSL "$1"
  fi
}

main() {
  local repo="${KALINKA_QOBUZ_REPO:-madenvel/kalinka-plugin-qobuz}"
  local sudo="" release fields tag version url sums_url name installed sums

  if [ "$(id -u)" -ne 0 ]; then
    have sudo || die "not root and 'sudo' not found — re-run as root"
    sudo="sudo"
  fi
  have apt-get || die "apt-get not found — the plugin installs on a Debian-based system only"
  have python3 || die "python3 is required (the Kalinka server needs it too)"
  have curl || die "curl is required"
  have sha256sum || die "sha256sum is required"

  echo ">> Looking up the latest release of $repo ..."
  release="$(api "https://api.github.com/repos/$repo/releases/latest")" \
    || die "could not query the latest release of $repo"

  # The tag, the .deb's URL and SHA256SUMS' URL, one per line.
  fields="$(python3 -c '
import json, sys
release = json.load(sys.stdin)
assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
debs = [n for n in assets if n.startswith(sys.argv[1] + "_") and n.endswith("_all.deb")]
print(release.get("tag_name", ""))
print(assets[debs[0]] if len(debs) == 1 else "")
print(assets.get("SHA256SUMS", ""))
' "$PACKAGE" <<<"$release")" || die "could not read the latest release of $repo"
  tag="$(sed -n 1p <<<"$fields")"
  url="$(sed -n 2p <<<"$fields")"
  sums_url="$(sed -n 3p <<<"$fields")"

  [ -n "$url" ] || die "release $tag has no single ${PACKAGE}_*_all.deb to install"
  [ -n "$sums_url" ] || die "release $tag has no SHA256SUMS to check the download against"
  name="${url##*/}"
  version="${name#"${PACKAGE}_"}"
  version="${version%_all.deb}"

  # Only a configured package counts: one left unpacked by a failed install is
  # installed again.
  installed="$(dpkg-query -W -f='${db:Status-Status} ${Version}' "$PACKAGE" 2>/dev/null || true)"
  case "$installed" in
    "installed "*) installed="${installed#installed }" ;;
    *) installed="" ;;
  esac
  if [ -n "$installed" ]; then
    if dpkg --compare-versions "$installed" ge "$version"; then
      echo ">> $PACKAGE $installed is installed; the latest release is $version. Nothing to do."
      return 0
    fi
    echo ">> Upgrading $PACKAGE $installed to $version"
  else
    echo ">> Installing $PACKAGE $version"
  fi

  # 0755, not mktemp's 0700, so apt's sandbox user can read the .deb.
  TMP="$(mktemp -d)"
  chmod 755 "$TMP"

  echo "   downloading $name"
  curl -fsSL -o "$TMP/$name" "$url"
  sums="$(curl -fsSL "$sums_url")" || die "could not download SHA256SUMS"
  sums="$(awk -v name="$name" '$2 == name' <<<"$sums")"
  [ -n "$sums" ] || die "the release's SHA256SUMS does not list $name"
  (cd "$TMP" && sha256sum --check --strict --quiet <<<"$sums") \
    || die "$name does not match the release's SHA256SUMS"
  echo "   checksum ok"

  # Waits for a dpkg lock held by, say, unattended-upgrades rather than failing.
  if ! $sudo apt-get -o DPkg::Lock::Timeout=300 install -y "$TMP/$name"; then
    echo >&2
    echo "If apt names kalinka-plugin-sdk above, this release does not fit the Kalinka" >&2
    echo "server installed here. Upgrade Kalinka if it is older than the range apt" >&2
    echo "printed; a newer Kalinka needs a newer release of this plugin." >&2
    return 1
  fi

  echo
  echo ">> Installed $PACKAGE $version. Kalinka restarts to load it."
}

main "$@"
