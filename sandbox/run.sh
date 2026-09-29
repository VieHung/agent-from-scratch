#!/bin/bash
# Phase 2: build + chạy sandbox
# Build and enter the same isolated image used by the CLI.
set -e
docker build -t agent-ubuntu:sandbox -f sandbox/Dockerfile .
docker run --rm -it --network none --read-only --user 1000:1000 \
  --mount "type=bind,src=$(pwd),dst=/workspace" \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --workdir /workspace --env HOME=/tmp agent-ubuntu:sandbox bash
