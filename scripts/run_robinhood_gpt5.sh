#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

source .venv/bin/activate

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="results/webagentbench/gpt5_robinhood_${TIMESTAMP}.json"
mkdir -p results/webagentbench

echo "Model:  gpt-5 via LiteLLM proxy"
echo "Mode:   baseline (71 Robinhood tasks)"
echo "Output: $OUTFILE"
echo ""

PYTHONUNBUFFERED=1 python -m webagentbench.agent_eval \
  --model gpt-5 \
  --provider openai \
  --api-key "$LITELLM_PROXY_API_KEY" \
  --api-base-url "$LITELLM_PROXY_URL" \
  --environments robinhood \
  --workers 10 \
  --seed 42 \
  --server-port 8083 \
  --output "$OUTFILE" \
  2>&1 | tee "${OUTFILE%.json}.log"
