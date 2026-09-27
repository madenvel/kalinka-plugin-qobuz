#!/usr/bin/env bash
# Regenerate the committed Qobuz Connect protobuf bindings (needs grpcio-tools).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-python3}"
DIR=src/kalinka_plugin_qobuz/connect/proto
"$PY" -m grpc_tools.protoc -I "$DIR" --python_out="$DIR" --pyi_out="$DIR" "$DIR/qws.proto" "$DIR/qconnect.proto"
echo "Regenerated $DIR/qws_pb2.py and $DIR/qconnect_pb2.py"
