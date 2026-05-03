#!/usr/bin/env bash
#SBATCH --job-name=pixel-opus-47
#SBATCH --partition=compsci
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=10G
#SBATCH --time=24:00:00
#SBATCH --output=/usr/xtmp/%u/wab-logs/pixel-opus-47-%j.out
#SBATCH --error=/usr/xtmp/%u/wab-logs/pixel-opus-47-%j.err

# Pixel-mode (BrowserGym + PixelLLMAgent, screenshot-only obs, coord
# action_space) sweep using opus 4.7 via AWS Bedrock. PrimBench v2
# never ran any model in pixel mode — this is the first opus pixel run.
# Defaults (--timeout 1200 --max-steps 60) are inherited from
# pixel_run_picks.py since commit dbc59360.

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
echo "=== opus 4.7 × pixel-vlm × $(python3 -c "import json; print(len(json.load(open('$PICKS'))))") picks ==="
echo "Job $SLURM_JOB_ID on $(hostname), backend :$BACKEND_PORT, picks=$PICKS"

# Pixel mode goes through BrowserGym's _ensure_server() which requires
# WEBAGENTBENCH_CONTROLLER_SECRET to be set when an externally-managed
# server is detected. Generate one here and inherit it into both the
# uvicorn child and the runner.
export WEBAGENTBENCH_CONTROLLER_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
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

OUT_DIR=/usr/xtmp/$USER/wab-runs/pixel-opus-47-${SLURM_JOB_ID}

export PYTHONUNBUFFERED=1
python -u scripts/pixel_run_picks.py \
  --picks "$PICKS" \
  --model us.anthropic.claude-opus-4-7 \
  --provider bedrock \
  --backend-port "$BACKEND_PORT" \
  --output-dir "$OUT_DIR"

echo
echo "=== Complete ($(date)) ==="
echo "Results at: $OUT_DIR"
