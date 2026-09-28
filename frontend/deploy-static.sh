#!/bin/sh
set -eu

TARGET="${STATIC_TARGET:-/static/vite}"

echo "Deploying frontend static assets to ${TARGET}..."
rm -rf "${TARGET}"
cp -r /vite "${TARGET}"
echo "Done."