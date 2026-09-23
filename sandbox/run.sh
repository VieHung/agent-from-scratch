#!/bin/bash
# Phase 2: build + chạy sandbox
# docker build -t agent-ubuntu:sandbox -f sandbox/Dockerfile .
# docker run --rm -it -v $(pwd):/work agent-ubuntu:sandbox
set -e
docker build -t agent-ubuntu:sandbox -f sandbox/Dockerfile .
docker run --rm -it --network none -v "$(pwd)":/work agent-ubuntu:sandbox
