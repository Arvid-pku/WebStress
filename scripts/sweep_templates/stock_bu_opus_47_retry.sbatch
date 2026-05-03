#!/usr/bin/env bash
#SBATCH --job-name=stock-bu-opus-47-retry
#SBATCH --partition=compsci
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH --time=24:00:00
#SBATCH --output=/usr/xtmp/%u/wab-logs/stock-bu-opus-47-retry-%j.out
#SBATCH --error=/usr/xtmp/%u/wab-logs/stock-bu-opus-47-retry-%j.err

# Re-run the 418 opus_4_7 tasks that hit the 600s wall-clock timeout in the
# original PrimBench v2 sweep. opus on Bedrock averages ~41s/step, so the old
# default (--timeout 600) clipped it to ~14 effective steps and killed 418 of
# 1038 tasks before they could complete. This template uses the new doubled
# defaults (1200s task / 240s step / 180s Chrome) — see commit dbc59360.
#
# Picks file: scripts/sweep_picks/opus_timeout_retry_418.json (committed)
# Source: scripts/aggregate_primbench_v2.py output, filtered to elapsed≥590
#         steps<40 success=False from /usr/xtmp/$USER/primbench-results-v2/opus_4_7/

set -euo pipefail
export HF_HOME=/usr/xtmp/$USER/.cache/huggingface
export TORCH_HOME=/usr/xtmp/$USER/.cache/torch
export PIP_CACHE_DIR=/usr/xtmp/$USER/.cache/pip
mkdir -p /usr/xtmp/$USER/wab-logs "$HF_HOME" "$PIP_CACHE_DIR"

ROOT=/home/users/tg295/projects/LLMOS
cd "$ROOT"
source .venv/bin/activate
set -a; source webagentbench/.env; set +a

BACKEND_PORT=$(( 9400 + (SLURM_JOB_ID % 600) ))
echo "=== opus 4.7 × stock-browser-use × 418-task timeout-retry ==="
echo "Job $SLURM_JOB_ID on $(hostname), backend :$BACKEND_PORT"

export WEBAGENTBENCH_AUTO_BUILD_FRONTENDS=0

python -m uvicorn webagentbench.app:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning \
  > /usr/xtmp/$USER/wab-logs/backend-${SLURM_JOB_ID}.log 2>&1 &
BPID=$!
trap "kill $BPID 2>/dev/null || true" EXIT INT TERM

READY=0
for i in $(seq 1 120); do
  curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1 && { READY=1; echo "backend ready after ${i}s"; break; }
  sleep 1
done
[ "$READY" = "0" ] && { echo "ERROR: backend /health never came up"; tail -40 /usr/xtmp/$USER/wab-logs/backend-${SLURM_JOB_ID}.log; exit 1; }

OUT_DIR=/usr/xtmp/$USER/wab-runs/stock-opus-47-retry-${SLURM_JOB_ID}

export PYTHONUNBUFFERED=1
# All timeout flags use the new doubled defaults — passed explicitly here so
# this sbatch is self-documenting if defaults are ever changed back.
python -u scripts/run_picks.py \
  --picks scripts/sweep_picks/opus_timeout_retry_418.json \
  --model us.anthropic.claude-opus-4-7 \
  --provider bedrock \
  --backend-port "$BACKEND_PORT" \
  --frontend-port "$BACKEND_PORT" \
  --max-steps 40 \
  --timeout 1200 \
  --step-timeout 240 \
  --concurrency 4 \
  --output-dir "$OUT_DIR"

echo
echo "=== Complete ($(date)) ==="
echo "Results at: $OUT_DIR"
