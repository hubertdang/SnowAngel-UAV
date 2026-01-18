#!/usr/bin/env bash
set -euo pipefail

echo "Building and launching the Ice Thickness Visualizer stack..."
docker compose up --build "$@"
