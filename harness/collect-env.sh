#!/usr/bin/env bash
set -euo pipefail

HOSTNAME="$(hostname)"
DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
CPU_COUNT="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "unknown")"
OS="$(uname -s)"
ARCH="$(uname -m)"
KERNEL="$(uname -r)"
DOCKER_VERSION="$(docker --version 2>/dev/null || echo "not installed")"
RUNNER_NAME="${RUNNER_NAME:-$HOSTNAME}"
RUNNER_OS="${RUNNER_OS:-$OS}"
RUNNER_ARCH="${RUNNER_ARCH:-$ARCH}"
GITHUB_SHA="${GITHUB_SHA:-unknown}"
GITHUB_RUN_ID="${GITHUB_RUN_ID:-unknown}"
GITHUB_RUN_ATTEMPT="${GITHUB_RUN_ATTEMPT:-unknown}"

# CPU model where available
if [ "$OS" = "Linux" ]; then
  CPU_MODEL="$(awk -F: '/model name/ {gsub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || echo "unknown")"
elif [ "$OS" = "Darwin" ]; then
  CPU_MODEL="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "unknown")"
else
  CPU_MODEL="unknown"
fi

# Total memory in MB
if [ "$OS" = "Linux" ]; then
  TOTAL_MEM="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo "unknown")"
elif [ "$OS" = "Darwin" ]; then
  TOTAL_MEM="$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1048576 ))"
else
  TOTAL_MEM="unknown"
fi

RUNNER_FINGERPRINT="${RUNNER_OS}|${RUNNER_ARCH}|cpu:${CPU_COUNT}|mem_mb:${TOTAL_MEM}|kernel:${KERNEL}"

printf '{"hostname":"%s","date":"%s","cpu_count":"%s","cpu_model":"%s","total_memory_mb":"%s","os":"%s","arch":"%s","kernel":"%s","docker_version":"%s","runner_name":"%s","runner_os":"%s","runner_arch":"%s","github_sha":"%s","github_run_id":"%s","github_run_attempt":"%s","runner_fingerprint":"%s"}\n' \
  "$HOSTNAME" "$DATE" "$CPU_COUNT" "$CPU_MODEL" "$TOTAL_MEM" "$OS" "$ARCH" "$KERNEL" "$DOCKER_VERSION" "$RUNNER_NAME" "$RUNNER_OS" "$RUNNER_ARCH" "$GITHUB_SHA" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT" "$RUNNER_FINGERPRINT"
