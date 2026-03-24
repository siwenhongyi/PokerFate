#!/usr/bin/env bash
# Compile proto files → Python pb2 modules.
# Run once after cloning the repo.
#
# Requires: pip install grpcio-tools
#
# Output: pf_intercept/pb/*_pb2.py

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/../pf_reverse/output/proto/Proto"
OUT_DIR="$SCRIPT_DIR/pb"

mkdir -p "$OUT_DIR"
touch "$OUT_DIR/__init__.py"

python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  "$PROTO_DIR"/*.proto

echo "Done. pb2 files written to $OUT_DIR"
