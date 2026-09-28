#!/bin/sh
set -eux

apt-get update
apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libmariadb-dev-compat \
    libmariadb-dev

rm -rf /var/lib/apt/lists/*