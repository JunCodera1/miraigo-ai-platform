#!/usr/bin/env bash
# Run a command under a hard memory cap so that a runaway model load kills
# *this* process instead of pushing the whole machine into the OOM killer.
#
#   scripts/run-capped.sh 900 python scripts/eval_asr.py ...
#
# Linux + systemd only. The cap is enforced by the kernel (cgroup v2):
#   MemoryMax       hard limit in MiB (first argument)
#   MemorySwapMax   0, so the process cannot hide in swap
#   oom_score_adj   1000, so it is the preferred victim if the machine runs out
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <max-memory-MiB> <command> [args...]" >&2
  exit 64
fi

limit_mb="$1"
shift

if ! command -v systemd-run >/dev/null 2>&1; then
  echo "run-capped: systemd-run not found; refusing to run uncapped" >&2
  exit 69
fi

exec systemd-run --user --scope --quiet \
  -p "MemoryMax=${limit_mb}M" \
  -p MemorySwapMax=0 \
  -- /bin/sh -c 'echo 1000 > /proc/self/oom_score_adj 2>/dev/null || true; exec "$@"' run-capped "$@"
