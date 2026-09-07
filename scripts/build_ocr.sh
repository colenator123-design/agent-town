#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$project_dir/bin"
export CLANG_MODULE_CACHE_PATH="/private/tmp/pikachu-agent-clang-cache"
export SWIFT_MODULECACHE_PATH="/private/tmp/pikachu-agent-swift-cache"
exec /usr/bin/swiftc "$project_dir/tools/vision_ocr.swift" -o "$project_dir/bin/vision-ocr"
