# WebAgentBench Results

This directory contains sample result and review artifacts checked into the repository.

## Current Contents

The current checkout includes reviewed JSON artifacts such as:

- `review_gpt54_apr1_board_briefing_state_tracking_stress.json`
- `review_gpt54_apr1_filter_architect_verification_stress.json`
- `review_gpt54_apr1_filter_repair_chain_backtracking_stress.json`
- `review_gpt54_apr1_forward_email_grounding_stress.json`
- `review_gpt54_apr1_search_and_star_planning_stress.json`
- `review_gpt54_apr1_thread_archaeology_exploration_stress.json`

These files are useful as:

- example evaluation artifacts
- manual review inputs
- regression references for specific tasks and stress variants

## What Is Not In This Checkout

This directory is not currently a full benchmark run registry. In particular, this checkout does not include:

- a canonical leaderboard
- a full current-iteration trajectory index
- archived aggregate result tables for every historical benchmark version

If you add new retained artifacts, prefer naming that makes the model, date, task, and variant obvious from the filename.
