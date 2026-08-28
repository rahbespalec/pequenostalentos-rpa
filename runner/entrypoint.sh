#!/bin/sh
set -eu
if ! docker image inspect rpa-job:latest >/dev/null 2>&1; then
  docker build -t rpa-job:latest /job
fi
exec python3 /runner/server.py
