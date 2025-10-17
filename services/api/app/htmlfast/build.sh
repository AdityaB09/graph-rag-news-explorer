#!/usr/bin/env bash
set -euo pipefail

# Build into ./build
mkdir -p build && cd build
cmake .. -DPYTHON_EXECUTABLE="$(which python)"
cmake --build . --config Release

# Locate built module (works whether CMake drops it in build/ or build/Release/)
MOD="$(ls -1 *.so Release/*.so 2>/dev/null | head -n 1 || true)"
if [ -z "${MOD:-}" ]; then
  echo "htmlfast .so not found!" >&2
  exit 1
fi

# Copy ONLY into /app/htmlfast (import path is set to include this dir)
cp -f "$MOD" ..

echo "htmlfast built and placed at /app/htmlfast/$(basename "$MOD")"
exit 0
