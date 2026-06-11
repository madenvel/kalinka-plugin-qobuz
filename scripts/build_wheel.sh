#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install --upgrade build setuptools-scm

# Resolve the version up front so a broken environment fails loudly here,
# instead of setuptools-scm silently mislabelling the wheel.
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: not a usable git checkout — cannot derive the version." >&2
    echo "Build from a real clone (and check ownership if running as another user)." >&2
    exit 1
fi

VERSION=$(python3 -m setuptools_scm)

case "${VERSION}" in
    *.dev*)
        echo "Warning: building untagged dev version ${VERSION}." >&2
        echo "If you expected a release build, check out the release tag first:" >&2
        echo "    git fetch --tags --force && git checkout kalinka-plugin-qobuz-v<X.Y.Z>" >&2
        echo "(--force matters: plain --tags will not update a tag that moved)" >&2
        ;;
esac

echo "Building wheel version: ${VERSION}"
python3 -m build --wheel

# Sanity check: the wheel on disk must carry the version we just resolved.
if [ ! -f "dist/kalinka_plugin_qobuz-${VERSION}-py3-none-any.whl" ]; then
    echo "Error: built wheel does not match resolved version ${VERSION}:" >&2
    ls dist/ >&2
    exit 1
fi
