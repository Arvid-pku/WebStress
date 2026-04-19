# WebAgentBench Frontier Tasks — Handoff

You are continuing systematic UI-verification of booking.com benchmark tasks. Prior agents tested all `easy` → `expert` difficulty tasks and fixed several task/site bugs along the way. Your scope: the remaining **frontier** difficulty tasks.

## Environment

- **Working dir**: `/home/users/tg295/projects/LLMOS`
- **Dev server**: runs on `http://localhost:8084/launch` (Booking env). User is SSH-tunneled to this port. Uvicorn backend is on `:8080`, Vite dev server for booking is on `:8084`.
- **Git branch**: `main`
- **User**: Tianchen Guan (Duke CS researcher, SSH session on compsci-login node). Workflow preference: **when eval fails, discuss with user first** to determine website bug vs. agent error before fixing. Do not silently apply fixes.
- **Today**: 2026-04-18

## Your task list (test these, in order)

All are `difficulty: frontier`. **Skip** the one already done: `booking_frontier_social_reviewer`.

1. `booking_frontier_account_overhaul` — Complete account overhaul
2. `booking_frontier_budget_optimizer` — Budget-constrained hotel selection
3. `booking_frontier_cancel_and_reorganize` — Cancel 3, rebook 2 cheaper, message, update list
4. `booking_frontier_complete_journey` — Search, compare, save, book, modify
5. `booking_frontier_everything` — Ultimate: profile, settings, payments, search, book, cancel, modify
6. `booking_frontier_family_planner` — Family trip: compare, book, preference, list
7. `booking_frontier_grand_tour` — 3-city grand tour (NYC/Paris/Tokyo)
8. `booking_frontier_loyalty_maximizer` — Book 3 discounted Genius properties
9. `booking_frontier_message_handler` — Read, reply, send messages and book
10. `booking_frontier_notification_master` — Process all notifications per type
11. `booking_frontier_payment_and_booking` — Add 3 payments, book 3 hotels each on different card
12. `booking_frontier_price_optimizer` — London price optimization (Genius + amenities + wallet)
13. `booking_frontier_reservation_manager` — Audit: cancel, modify, message, review, save
14. `booking_frontier_saved_list_curator` — 3 themed lists, populate, book cheapest

Read each task's YAML at `webagentbench/tasks/booking/<task_id>.yaml` first. Frontier tasks are large (30–50+ steps) with many interleaved constraints — slow down and map out seed targets vs. decoys before acting.

## Verification protocol — MUST USE UI

**Absolute rule**: tasks must be solvable by a human via the UI. Do not drive state via API POST/PUT/DELETE. API is **read-only** (inspect state after each UI action to verify).

**Required flow per task**:

1. Navigate to `http://localhost:8084/launch` via `mcp__browser-use__browser_navigate`
2. Type task name fragment into the search input, click the task row, click **Launch**
3. Drive every state change via `mcp__browser-use__browser_click` / `browser_type` / `browser_get_state`
4. Click the floating **WAB** button (bottom-right), then **Evaluate** in the panel
5. Screenshot the result and report score

**If a step can't be completed via the UI**: STOP and ask the user. Don't assume it's a task bug. Possible causes:

- Your misunderstanding of the UI (ask)
- A real site bug needing a fix (discuss before fixing)
- Browser-use limitation (need to scroll first, stale element index, etc.)

## Known bug patterns (prior agents fixed these for simpler tasks — watch for them)

### 1. Review side-effect on reservations
Writing a review flips `rating_submitted: False → True` on the underlying reservation. If the task has an unfiltered `state.reservations preserve: ALL` invariant, this trips `[FAIL] Agent did not modify reservations`.

**Fix template**:
```yaml
seed:
  targets:
    res_id_X: '{output.res_id_X}'   # add for each reviewed reservation
canonical_diff:
  update:
    - entity: Reservation
      desc: Review submission flips rating_submitted on the reviewed reservation
      where:
        id: {expr: "x == target['res_id_X']"}
      changes:
        rating_submitted: {any: true}
  invariant:
    - collection: state.reservations
      filter: "a.id not in (target['res_id_1'], target['res_id_2'], ...)"
      preserve: ALL
```

**Critical**: after adding `update` entries, the matching invariant **must** have a filter excluding those IDs. Otherwise the registry validator refuses to load and uvicorn crashes on startup (`ValueError: invariant overlaps with positive diff target and has no filter`).

### 2. Default payment card flip
Setting a new default payment card unsets `is_default` on the previously-default card. If the payment_methods invariant preserves old cards, this trips.

**Fix**: add an `update` entry for the demoted card's `is_default` flip, similar to above.

### 3. Dietary restrictions case
UI checkbox labels are capitalized (`Halal`, `Vegan`); internal storage is lowercase (`halal`, `vegan`). This was fixed in `Settings.tsx` via `{label, value}` pairs, but if a frontier task specifies exact casing, double-check.

### 4. Pool amenity label mismatch
Search filter checkbox label is `"Pool"` (not `"Swimming Pool"`) in `SearchResults.tsx:56`. Seed data uses `"Pool"`. If you see 0 results after ticking the pool filter, that's not this bug — it's already fixed.

### 5. Dates don't propagate from search to property page
After clicking "See availability" on a search result, the property page **drops check-in/check-out** from the URL. You must re-enter dates in the property page's date inputs **before** clicking Reserve — otherwise you book 1 night and fail `nights: {eq: N}`.

### 6. Profile API field names
The `/api/env/booking/account` PUT endpoint expects `owner_phone`, `owner_address`, `owner_nationality` — not `phone`/`address`/`nationality`. (This only matters if you're using curl for read-only checks — don't use PUT anyway.)

## Backend reload — critical

After editing a YAML task file:
```bash
touch /home/users/tg295/projects/LLMOS/webagentbench/backend/seeders/booking.py
```

Then **wait for reload**:
```bash
until curl -sS --max-time 3 -X POST "http://localhost:8084/api/env/booking/session" \
  -H "Content-Type: application/json" \
  -d '{"task_id":"<any_valid_task_id>"}' 2>/dev/null | grep -q session_id; do sleep 3; done
```
Reload takes 60–120 seconds (task registry validates all YAMLs). If the server returns connection-refused after reload, a YAML you wrote has a validation error. Fix it, then ask the user to restart via `./scripts/webagentbench.sh dev --env booking`.

Vite hot-reloads `.tsx` automatically. `.py` and `.yaml` require the touch above.

## Browser-use MCP quirks

Full skill at `~/.claude/skills/browser-use-mcp/SKILL.md`. Key points:

- **First call may time out** with `BrowserStartEvent#XXX timed out after 30.0s` due to stale Singleton lock files from prior SSH sessions on NFS-shared `$HOME`. Fix:
  ```bash
  rm ~/.config/browseruse/profiles/default/Singleton{Lock,Cookie,Socket}
  ```
  Then ask the user to **reconnect the MCP** via `/mcp → Reconnect`. Retry after reconnect.
- **HTML5 date inputs**: type in `YYYY-MM-DD` format (not `MM/DD/YYYY`).
- **`<select>` elements**: `browser_type` with the option **value** (e.g. type `"1"` to select `<option value="1">`). There is no `browser_select_option`.
- **Deferred tool loading**: browser-use tools appear as names only. Before first use, load schemas via `ToolSearch` with `query: "select:mcp__browser-use__browser_navigate,mcp__browser-use__browser_click,mcp__browser-use__browser_type,mcp__browser-use__browser_get_state,mcp__browser-use__browser_screenshot,mcp__browser-use__browser_scroll,mcp__browser-use__browser_extract_content"`.
- **Element indices are session-scoped and ephemeral**. Re-call `browser_get_state` after navigation or after the page rerenders to get fresh indices.
- **Element not found / stale index**: after a UI action the indices renumber. If a click returns "Element with index X not found", re-get state.
- **Scrolling**: the task pane on the launch page is tall. Use `browser_scroll` if the target task isn't visible after typing a search filter.

## Per-task reporting format

For each task, report:
- **Title + task_id**
- **Seed targets vs. decoys** (which property/reservation/message/notification is the true target)
- **UI steps performed** (concise list — e.g., "Settings → Save Preferences → My Trips → Cancel res_1 → New Message to Grand Hotel → Send → ...")
- **Eval result** (score, pass/fail summary)
- If failed, **hypothesis** (what tripped, why, which layer) — then **stop for user confirmation before fixing**

## Read-only API inspection cheat sheet

```bash
SID="booking_..."  # from URL after launch
B="http://localhost:8084/api/env/booking"

curl -s "$B/reservations?session_id=$SID" | python3 -m json.tool
curl -s "$B/reservations/res_1?session_id=$SID" | python3 -m json.tool
curl -s "$B/payment-methods?session_id=$SID" | python3 -m json.tool
curl -s "$B/settings?session_id=$SID" | python3 -m json.tool
curl -s "$B/preferences?session_id=$SID" | python3 -m json.tool
curl -s "$B/notifications?session_id=$SID" | python3 -m json.tool
curl -s "$B/messages?session_id=$SID" | python3 -m json.tool
curl -s "$B/saved-lists?session_id=$SID" | python3 -m json.tool
curl -s "$B/reviews?session_id=$SID" | python3 -m json.tool
curl -s "$B/account?session_id=$SID" | python3 -m json.tool
curl -s "$B/properties/<prop_id>?session_id=$SID" | python3 -m json.tool

# Dump full eval result (useful for exact failure messages)
curl -s -X POST "$B/evaluate" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID\"}" | python3 -m json.tool
```

**DO NOT** use POST/PUT/DELETE to drive task state — use the browser.

## Frontier-specific tips

- **Long tasks = long contexts**. After each major step, verify state via curl so you can catch an off-by-one before cascading.
- **Many decoys**: frontier tasks seed 10–15 distractor properties/reservations/messages to confuse you. Always read the YAML seed block first to know which are real targets (via `target.*` references).
- **Constraint checks** (the `constraints:` section in canonical_diff) evaluate Python expressions against the full state. A single typo in e.g. a preference value will fail a constraint. Read each check's `expr` before driving the UI.
- **State-mutation order matters** in some tasks (e.g. add payment → set default → use for booking). Follow the instruction order.

## Memory system note

`~/.claude/projects/-home-users-tg295-projects-LLMOS/memory/` holds user/project memory. Update `MEMORY.md` as you discover new facts about the user or the project. See the auto-memory instructions in your system prompt.

## Start here

Begin with `booking_frontier_account_overhaul`. Read its YAML in full, identify the target property/reservation/message/notification, then drive the UI step-by-step. Report back after each task so the user can sanity-check before you advance.
