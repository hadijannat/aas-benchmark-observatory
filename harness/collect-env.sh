#!/usr/bin/env bash
set -euo pipefail

HOSTNAME="$(hostname)"
DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
CPU_COUNT="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "unknown")"
OS="$(uname -s)"
ARCH="$(uname -m)"
DOCKER_VERSION="$(docker --version 2>/dev/null || echo "not installed")"

# Total memory in MB
if [ "$OS" = "Linux" ]; then
  TOTAL_MEM="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "unknown")"
elif [ "$OS" = "Darwin" ]; then
  TOTAL_MEM="$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1048576 ))"
else
  TOTAL_MEM="unknown"
fi

printf '{"hostname":"%s","date":"%s","cpu_count":"%s","total_memory_mb":"%s","os":"%s","arch":"%s","docker_version":"%s"}\n' \
  "$HOSTNAME" "$DATE" "$CPU_COUNT" "$TOTAL_MEM" "$OS" "$ARCH" "$DOCKER_VERSION"
