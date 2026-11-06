#!/usr/bin/env bash
# Compile proto files → Python pb2 modules.
# Run once after cloning the repo.
#
# Requires: pip install grpcio-tools
#
# Output: pf_intercept/wire/pb/*_pb2.py

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/../../pf_reverse/output/proto/Proto"
OUT_DIR="$SCRIPT_DIR/../wire/pb"
PYTHON_BIN="${PYTHON:-}"

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/../../.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

mkdir -p "$OUT_DIR"
touch "$OUT_DIR/__init__.py"

"$PYTHON_BIN" -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  "$PROTO_DIR"/*.proto

echo "Done. pb2 files written to $OUT_DIR"
