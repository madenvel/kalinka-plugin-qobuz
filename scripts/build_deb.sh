#!/usr/bin/env bash
set -euo pipefail

PLUGIN_SLUG="kalinka-plugin-qobuz"

echo "Building .deb package for ${PLUGIN_SLUG} using setuptools_scm for version detection"

# Clean up previous build
rm -rf pkgroot/
mkdir -p pkgroot/opt/kalinka/wheels
mkdir -p pkgroot/DEBIAN

# Build wheel first to generate version
echo "Building wheel first to detect version..."
./scripts/build_wheel.sh

# Extract version from the generated _version.py file
if [ ! -f "src/kalinka_plugin_qobuz/_version.py" ]; then
    echo "Error: _version.py not found. Build wheel first." >&2
    exit 1
fi

# Extract version from the built wheel filename using sed
WHEEL_PATH=$(ls dist/*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL_PATH" ] || [ ! -f "$WHEEL_PATH" ]; then
    echo "Error: No wheel could be built." >&2
    exit 1
fi

VERSION=$(basename "$WHEEL_PATH" | sed 's/kalinka_plugin_qobuz-\(.*\)-py3-none-any\.whl/\1/')

PLUGIN_WHEEL="kalinka_plugin_qobuz-${VERSION}-py3-none-any.whl"

echo "Detected version: ${VERSION}"
echo "Expected wheel: ${PLUGIN_WHEEL}"

# Check if wheel exists
if [ ! -f "dist/${PLUGIN_WHEEL}" ]; then
    echo "Error: Wheel file dist/${PLUGIN_WHEEL} not found" >&2
    echo "Available wheels:"
    ls -la dist/ || echo "No dist directory found"
    exit 1
fi

# Copy wheel to package root
cp "dist/${PLUGIN_WHEEL}" "pkgroot/opt/kalinka/wheels/"

# Generate control file from template
sed "s/@VERSION@/${VERSION}/g" debian/control.in > pkgroot/DEBIAN/control

# Generate postinst script from template
sed "s/@VERSION@/${VERSION}/g" debian/postinst > pkgroot/DEBIAN/postinst

# Copy prerm script
cp debian/prerm pkgroot/DEBIAN/prerm

# Make scripts executable
chmod 755 pkgroot/DEBIAN/postinst
chmod 755 pkgroot/DEBIAN/prerm

# Build the .deb package
dpkg-deb --root-owner-group --build pkgroot "${PLUGIN_SLUG}_${VERSION}_all.deb"

echo "Package built: ${PLUGIN_SLUG}_${VERSION}_all.deb"
ls -l "${PLUGIN_SLUG}_${VERSION}_all.deb"