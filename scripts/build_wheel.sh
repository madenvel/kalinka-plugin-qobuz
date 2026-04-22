#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade build setuptools-scm
python3 -m build --wheel
