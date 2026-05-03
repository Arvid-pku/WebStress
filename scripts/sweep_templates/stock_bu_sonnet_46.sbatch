#!/usr/bin/env bash
#SBATCH --job-name=stock-bu-sonnet-46
#SBATCH --partition=compsci
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH --time=24:00:00
#SBATCH --output=/usr/xtmp/%u/wab-logs/stock-bu-sonnet-46-%j.out
#SBATCH --error=/usr/xtmp/%u/wab-logs/stock-bu-sonnet-46-%j.err

# Stock browser-use sweep over the full PrimBench v2 dispatch set (1038
# task × cond pairs) using sonnet-4-6 via AWS Bedrock. Same model_id /
# provider that sonnet was run with in earlier rounds (look for
# webagentbench/results/sonnet_4_6_full_openrouter*/ in .gitignore).
#
# Required: full picks JSON. The PrimBench v2 picks file is built from
# the task registry — see webagentbench/docs/RUNNING_SWEEPS.md for the
# regen recipe (one-liner via webagentbench.tasks).
#
# Edit PICKS to point to whatever picks file you want to sweep.

set -euo pipefail
export HF_HOME=/usr/xtmp/$USER/.cache/huggingface
export TORCH_HOME=/usr/xtmp/$USER/.cache/torch
export PIP_CACHE_DIR=/usr/xtmp/$USER/.cache/pip
mkdir -p /usr/xtmp/$USER/wab-logs "$HF_HOME" "$PIP_CACHE_DIR"

ROOT=/home/users/tg295/projects/LLMOS
cd "$ROOT"
source .venv/bin/activate
set -a; source webagentbench/.env; set +a

# >>> EDIT this to your picks file <<<
PICKS="${PICKS:-scripts/sweep_picks/primbench_v2_full_1038.json}"
[ -f "$PICKS" ] || { echo "ERROR: picks file $PICKS not found. See RUNNING_SWEEPS.md for regen."; exit 1; }

BACKEND_PORT=$(( 9400 + (SLURM_JOB_ID % 600) ))
echo "=== sonnet-4-6 × stock-browser-use × $(python3 -c "import json; print(len(json.load(open('$PICKS'))))") picks ==="
echo "Job $SLURM_JOB_ID on $(hostname), backend :$BACKEND_PORT, picks=$PICKS"

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

OUT_DIR=/usr/xtmp/$USER/wab-runs/stock-sonnet-46-${SLURM_JOB_ID}

export PYTHONUNBUFFERED=1
# Defaults (--timeout 1200 --step-timeout 240 --max-steps 40) are inherited
# from run_picks.py since commit dbc59360. Override here only if needed.
python -u scripts/run_picks.py \
  --picks "$PICKS" \
  --model us.anthropic.claude-sonnet-4-6 \
  --provider bedrock \
  --backend-port "$BACKEND_PORT" \
  --frontend-port "$BACKEND_PORT" \
  --concurrency 4 \
  --output-dir "$OUT_DIR"

echo
echo "=== Complete ($(date)) ==="
echo "Results at: $OUT_DIR"
