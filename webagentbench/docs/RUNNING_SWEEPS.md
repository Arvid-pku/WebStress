# Running PrimBench Sweeps

Copy-paste-ready commands for the three sweep scenarios that come up most often.
All templates use the doubled wall-clock defaults from commit `dbc59360`
(per-task timeout 1200s, per-step 240s, Chrome boot 180s, pixel max-steps 60).
You shouldn't need to override any timeout flags unless you're testing edge cases.

## Prerequisites (one-time)

```bash
# 1. API keys — fill in webagentbench/.env (template: webagentbench/.env.template)
#    Required keys per scenario:
#      stock + opus/sonnet  → AWS_BEDROCK_API_KEY
#      pixel + opus         → AWS_BEDROCK_API_KEY
#      pixel + gemini       → GEMINI_API_KEY
#
# 2. Frontends built (one-time):
bash scripts/webagentbench.sh build

# 3. Picks file (regenerated on demand):
source .venv/bin/activate
python scripts/gen_picks.py --subset all -o scripts/sweep_picks/primbench_v2_full_1038.json
# Produces 519 clean + 530 intervention = 1049 unique (task_id, cond) pairs.
# Note: PrimBench v2's analysis aggregator works with 1038 dispatch keys after
# de-duplication of intervention variants — see scripts/aggregate_primbench_v2.py
```

---

## Scenario 1 — Re-run opus_4_7's 418 timeout failures

The original PrimBench v2 sweep used `--timeout 600` and clipped opus
(~41s/step on Bedrock) to ~14 effective steps. 418 of 1038 opus tasks hit
`elapsed >= 590s` before completing. The new defaults (`--timeout 1200
--step-timeout 240`) give opus a real chance.

The picks file is committed at `scripts/sweep_picks/opus_timeout_retry_418.json`.

```bash
sbatch scripts/sweep_templates/stock_bu_opus_47_retry.sbatch
```

**What to expect:**
- 4-way concurrent, 418 tasks × ~10 min each / 4 ≈ ~17h walltime (sbatch reserves 24h)
- Cost: ~$80-100 in Bedrock charges
- Output: `/usr/xtmp/$USER/wab-runs/stock-opus-47-retry-<JOBID>/`
- Verify success: open `summary.json`, expect `passed > 200` (vs 0 in original failed batch)

**To re-aggregate with the original PrimBench v2 results:**
```bash
# Combine the original opus_4_7 dir with new retry results
cp -r /usr/xtmp/$USER/wab-runs/stock-opus-47-retry-<JOBID>/tasks/* \
      /usr/xtmp/$USER/primbench-results-v2/opus_4_7/tasks/
python scripts/aggregate_primbench_v2.py \
  --root /usr/xtmp/$USER/primbench-results-v2 \
  --out  /usr/xtmp/$USER/primbench-aggregate-v2-with-retry
```

---

## Scenario 2 — Stock browser-use sweep with sonnet-4-6

```bash
# Generate full picks (one-time)
python scripts/gen_picks.py --subset all -o scripts/sweep_picks/primbench_v2_full_1038.json

# Submit
sbatch scripts/sweep_templates/stock_bu_sonnet_46.sbatch

# Or override picks via env var (e.g. smoke subset)
PICKS=scripts/sweep_picks/my_smoke.json sbatch scripts/sweep_templates/stock_bu_sonnet_46.sbatch
```

**Model id / provider used:** `us.anthropic.claude-sonnet-4-6` via `bedrock`.
The Bedrock entrypoint is in `webagentbench/stock_browseruse_eval.py:553-571` and
uses the `ChatAWSBedrockForced` adapter (forces `toolChoice=any` so models
can't return plain text instead of structured tool_use).

**What to expect:**
- 1049 picks × ~3 min each / 4-way = ~13h walltime
- Cost: ~$50-70 in Bedrock charges
- Output: `/usr/xtmp/$USER/wab-runs/stock-sonnet-46-<JOBID>/`

---

## Scenario 3 — Pixel-mode sweeps

Pixel mode runs through BrowserGym with screenshot-only obs and coord-action
output. PrimBench v2 has no pixel data yet — these are first runs.

### 3a. Pixel + opus 4.7

```bash
sbatch scripts/sweep_templates/pixel_opus_47.sbatch
```

**Model id / provider:** `us.anthropic.claude-opus-4-7` via `bedrock`.

**What to expect:**
- Cost-heavy due to per-step screenshot in tokens; budget ~$150-200 / 1049 picks
- Walltime ~15h (pixel ~1.5× slower than stock)
- Output: `/usr/xtmp/$USER/wab-runs/pixel-opus-47-<JOBID>/`

### 3b. Pixel + gemini-3-pro-preview

```bash
sbatch scripts/sweep_templates/pixel_gemini_31_pro.sbatch
```

**Model id / provider:** `gemini-3-pro-preview` via `gemini` (native API).
Coordinates are normalized 0-1000 → pixel transform happens in
`pixel_agent.py:_transform_normalized_to_pixel`.

**What to expect:**
- Much cheaper than opus pixel (~$10-20 / 1049 picks)
- Walltime ~6h
- Output: `/usr/xtmp/$USER/wab-runs/pixel-gemini-31-pro-<JOBID>/`

---

## Important: pixel-mode controller secret

Both pixel templates set `WEBAGENTBENCH_CONTROLLER_SECRET` automatically. If
you launch `pixel_run_picks.py` manually outside these templates and see:

```
RuntimeError: A WebAgentBench server is already running, but
WEBAGENTBENCH_CONTROLLER_SECRET is not set in this process.
```

…export a secret before invoking the runner:
```bash
export WEBAGENTBENCH_CONTROLLER_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
```

This is needed because `BrowserGym.browsergym_task._ensure_server()` rejects
externally-managed backends without this secret (anti-collision guard).

---

## Bedrock TPM throttling (avoid running opus + sonnet sweeps in parallel)

Verified during smoke: opus-4-7 and sonnet-4-6 share the same Bedrock TPM
quota on us-east-1. Launching both sbatch sweeps in the same window will
throttle the second one's credential probe (`PixelLLMAgent.__init__`) or
mid-run LLM calls (`ModelRateLimitError: Too many tokens`). Symptoms:

```
RuntimeError: PixelLLMAgent credential probe FAILED for provider='bedrock'
  ThrottlingException: Too many tokens, please wait before trying again
```

Sequential strategy (recommended):
```bash
# Submit opus first
JOB1=$(sbatch --parsable scripts/sweep_templates/stock_bu_opus_47_retry.sbatch)
# Submit sonnet to start AFTER opus completes
sbatch --dependency=afterany:$JOB1 scripts/sweep_templates/stock_bu_sonnet_46.sbatch
```

Or just stagger by ~6 hours manually. Pixel + opus + concurrency=4 will
also self-throttle within the same job — bring `--concurrency` down to 2.

## After a sweep finishes

```bash
# Quick sanity check
cat /usr/xtmp/$USER/wab-runs/<job-output-dir>/summary.json | jq '.n, .passed, .avg_score'

# Re-aggregate alongside other models
python scripts/aggregate_primbench_v2.py \
  --root <dir-containing-per-model-subdirs> \
  --out  <aggregate-output-dir>

# View one trajectory
python -m webagentbench.visualize \
  /usr/xtmp/$USER/wab-runs/<job>/tasks/<task_id>__<cond>/trajectory.json
```

## Debugging a stuck job

```bash
# Tail backend log (was the uvicorn child OK?)
tail -200 /usr/xtmp/$USER/wab-logs/backend-<JOBID>.log

# Tail runner log (was the picks loop progressing?)
tail -200 /usr/xtmp/$USER/wab-logs/<sbatch-name>-<JOBID>.out

# Check sbatch resource usage
sacct -j <JOBID> --format=JobID,Elapsed,MaxRSS,State
```
