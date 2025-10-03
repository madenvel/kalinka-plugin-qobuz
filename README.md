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

## Configuration

After installation, the plugin appears in Kalinka's configuration interface where you can:
- Enable/disable the plugin
- Configure plugin-specific settings
- Test the plugin functionality

## Development

### Testing
Run the included smoke tests:

```bash
pytest tests/
```

## License

This plugin is released under the GPL-3.0-or-later license.

## Support

For questions about this plugin or plugin development in general:
- Check the Kalinka Plugin SDK documentation
- Review other plugins in the ecosystem
- Consult the main Kalinka project documentation
