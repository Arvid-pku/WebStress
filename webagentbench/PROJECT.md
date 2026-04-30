# PrimBench: Diagnosing Cognitive Primitives of Web Agents via Environment Interventions

A diagnostic benchmark that decomposes web-agent competence into **seven cognitive primitives** and stresses each one through controlled environment interventions. Seven interactive environments, 519 base tasks, 530 intervention variants, deterministic scoring against server state.

| | Count |
|---|---|
| Environments | 7 |
| Base Tasks | 519 |
| Intervention Variants | 530 |
| Primitives | 7 |
| Injection Layers | 4 |
| Intervention Families | 29 |

---

## Table of Contents

1. [Motivation](#1-motivation)
2. [Conceptual Hierarchy: Variant ↔ Primitive ↔ Family ↔ Dispatch ↔ Layer](#2-conceptual-hierarchy)
3. [The Seven Cognitive Primitives](#3-the-seven-cognitive-primitives)
4. [The Four Injection Layers](#4-the-four-injection-layers)
5. [Worked Example: A Patience Intervention](#5-worked-example-a-patience-intervention)
6. [Catalog Map: 29 Families across 4 Layers](#6-catalog-map-29-families-across-4-layers)
7. [Design Invariants](#7-design-invariants)
8. [Evaluation System](#8-evaluation-system)
9. [Evaluated Agents](#9-evaluated-agents)
10. [Human Baseline](#10-human-baseline)
11. [Environments](#11-environments)
12. [Repository Structure](#12-repository-structure)
13. [Running PrimBench](#13-running-primbench)

---

## 1. Motivation

Existing web-agent benchmarks score whole-task completion. A run either succeeds or fails, and a single scalar gets reported. The scalar is useful for ranking models, yet it carries almost no diagnostic information. When an agent finishes a 15-step checkout with score 0, the log does not say whether the agent misread a product card, accepted a forged "Saved" toast, abandoned a retry after a transient 503, or walked past the only remaining affordance. The benchmark does not know, and the training signal that follows does not know either.

What we actually want to measure is a set of **cognitive primitives**: the atomic capabilities a web user exercises across every domain. A competent user grounds an observation, plans sub-goals, tracks state, backtracks on a bad decision, waits out a flaky request, explores when the obvious path disappears, and verifies that an action took effect. A benchmark that exposes each primitive independently lets a developer read a model profile, identify the weakest axis, and target training at that axis. Whole-task benchmarks flatten this profile into a single number and obscure the gradient.

PrimBench addresses the gap through **environment interventions**. We take a well-formed base task, apply a controlled perturbation that stresses exactly one primitive, and grade the outcome against the same success criterion as the baseline. A drop between baseline and intervention isolates the failing primitive, because everything else in the environment is held fixed. The intervention is the experimental manipulation; the primitive is the dependent variable.

> **One-line summary.** Replace "did the agent finish the task" with "for each primitive, did the agent withstand a targeted stressor." The first number ranks; the second number trains.

---

## 2. Conceptual Hierarchy

PrimBench's terminology is layered. From the most concrete (a single YAML file) to the most abstract (a research goal):

```
Intervention Variant (530)   ← one YAML = (base_task) × (one dispatch)
        │
        │ targets exactly one
        ▼
Primitive (7)                ← the cognitive ability being stressed
        ▲
        │ stressed by
        │
Family (29)                  ← conceptual grouping of stressor mechanisms
        │
        │ implemented by 1+
        ▼
Dispatch (48)                ← real callable code branch
        │
        │ each lives in exactly one
        ▼
Layer (4: Seed, Server, Network, Client)
                             ← where the perturbation fires in the web stack
```

### What each level is for

| Level | Role | Where you see it |
|---|---|---|
| **Variant** | A YAML file at `injector/variants/` that pairs a base task with one dispatch + parameters. | `booking_expert_compare_and_decide__property_shadow_v2.yaml` |
| **Primitive** | The dependent variable. The cognitive ability you want to measure on a scale (e.g., Grounding). Each variant declares one `target_primitive`. | `target_primitive: grounding` |
| **Family** | A conceptual grouping of dispatches that share a stressor mechanism. The right unit for reasoning about coverage. | "Decoys & aliases" |
| **Dispatch** | The real callable in `injector/{seed,server,middleware,network}.py` or `BenchmarkToolbar.tsx`. The string in `params.action`. | `add_confusing_decoys` |
| **Layer** | Where the dispatch fires in the web stack. Determines the file and the timing. | `seed` |

### Worked example of one variant in all five terms

| Field | Value |
|---|---|
| **Variant file** | `booking_expert_compare_and_decide__property_shadow_v2.yaml` |
| **Primitive** | `grounding` (can the agent pick the real Rosewood London among near-identical decoys?) |
| **Family** | "Decoys & aliases" |
| **Dispatch** | `add_confusing_decoys` |
| **Layer** | `seed` (decoy hotels written into `state.properties` at session creation) |

### Why a separate Family vs Dispatch?

Families are the conceptual unit; dispatches are the implementation unit. The 48 dispatches collapse into 29 families for two reasons:

1. **Environment-specific specialisations** — `add_decoy_notifications` and `add_noise_orders` both inject noise (same family, "Decoys & aliases"), but one writes to the notification list and the other to the orders list. They share a mechanism but read from different state collections.
2. **Behaviour modes inside one dispatch** — the `delay` dispatch alone collapses six behaviour modes (`once`, `intermittent`, `progressive`, `tail_latency`, `correlated_window`, `write_only_slow`). Together they form the "Latency" family.

When you talk to a reviewer, count families (29). When you read a `git diff`, count dispatches (48).

---

## 3. The Seven Cognitive Primitives

We settled on seven primitives. Two constraints guided the choice:

1. The set should **cover** every failure mode reported in recent agent studies.
2. The primitives should **not overlap** semantically, so that a failure on a targeted intervention cannot be attributed to more than one primitive.

| Primitive | What it measures | Stressed by |
|---|---|---|
| **Grounding** | Map observation to the correct semantic understanding of the UI. Pick the real target when decoys, near-lookalikes, adversarial content, or mislabeled controls are present. | phishing emails, alias entities, label-input misalignment, distractor modals |
| **Planning** | Decompose a goal into ordered sub-goals and respect dependencies between them. Keep the plan consistent as new information arrives. | scrambled timestamps, missing prerequisites, stale first-search results |
| **State Tracking** | Maintain a working model of what is done versus pending across a multi-step trajectory. Reconcile updates that arrive out of order. | shuffled contacts, split information, contradictory updates, repeated-contradicted haystacks |
| **Backtracking** | Detect a failure, revert to a prior decision point, and try an alternative. Recognize that the current path is blocked rather than retry the same action. | session expiry (401), 409 conflicts, planted wrong answer, skeleton that never resolves |
| **Patience** | Know when to wait. Calibrate retry timing through slow, flaky, or rate-limited operations, and distinguish a loading state from a failure. | tail latency, progressive delays, rate limits (429 + Retry-After), correlated slow windows |
| **Exploration** | Discover alternative affordances and paths when the obvious one fails. Try the non-default entry point rather than abandon the task. | restrict_affordance_set (only one of image/title works), hidden prerequisites, intercepting overlays |
| **Verification** | After performing an action, check that it actually achieved its intended effect. Do not take a success banner at face value. | silent_fail, misleading_success (toast reads "Saved"), click_swallow, save_drift, input_corruption |

### Coverage and Non-Overlap

Each variant names exactly one `target_primitive`. The catalog enforces the invariant `|task.primitives ∪ {variant.target_primitive}| ≤ 2`, which caps confounding at the (task, variant) level. A failure on a verification-targeted variant therefore reflects verification, holding the grounding demand of the base task fixed.

Each primitive maps to a disjoint set of stressor classes, ensuring measurement is clean:

| Primitive | Primary stressor class | Representative dispatches |
|---|---|---|
| Grounding | Adversarial or near-identical content | `inject_adversarial_content`, `add_confusing_decoys`, `label_input_misalignment` |
| Planning | Disordered prerequisites | `scramble_timestamps`, `hide_prerequisite` |
| State Tracking | Divergent or fragmented state | `split_information`, `add_contradictory_update`, `shuffle_positions` |
| Backtracking | Hard failure requiring alternative | `session_expiry`, `concurrent_modification`, `plant_wrong_answer` |
| Patience | Latency or rate pressure | `delay` (tail_latency, progressive), `rate_limit` |
| Exploration | Closed default path | `restrict_affordance_set`, `hide_in_non_obvious_location`, `intercepting_overlay` |
| Verification | False positive feedback | `silent_fail`, `misleading_success`, `save_drift`, `click_swallow` |

---

## 4. The Four Injection Layers

An intervention is not a single mechanism. A phishing email and a 503 retry and a swallowed click are all interventions, but they live at different places in the web stack and fire at different times. Collapsing them into one hook would either paper over real mechanisms (DOM mocks of network failure miss real HTTP timing) or miss mechanisms entirely (a middleware has no view of DOM occlusion). PrimBench therefore splits the perturbation space by *where* each action fires.

### Why Four Layers Are Needed

| Layer | Captures | Cannot be expressed by the others |
|---|---|---|
| **Seed** | Content semantics before the session starts (phishing, decoys, adversarial bodies). | A network hook cannot rewrite the initial dataset the SPA seeds from; a client hook comes too late. |
| **Server** | Structural properties of state (ordering, timestamps, hidden labels). | The SPA consumes server state at boot; client-level shuffling is visible to refresh and easy to undo. |
| **Network** | Real HTTP timing and status (503, 429, 401, silent 200). | Client code cannot forge a Retry-After header that survives a page refresh, and seed data cannot cause latency. |
| **Client** | Interaction fidelity at the DOM (swallowed clicks, label drift, typed-input corruption, overlays). | Network and server see write intent, not whether the click that produced it landed on the right element. |

### When Each Layer Fires

```
Seed                    Server                  Network             Client
(once, at session       (once, after seed)      (per request)       (per interaction)
 creation)
   │                      │                       │                    │
   │ injector/seed.py     │ injector/server.py    │ injector/         │ shared/src/components/
   │                      │                       │ middleware.py     │ BenchmarkToolbar.tsx
   ▼                      ▼                       ▼                    ▼
data mutations         structural mutations    HTTP middleware     DOM hooks
(decoy properties,    (shuffle ordering,      (delay, 503, 429,   (swallowed clicks,
 phishing emails,      scramble timestamps,    silent_fail,        label drift,
 adversarial content,  hide labels,            session_expiry)     intercepting
 split information)    corrupt fields)                             overlays)
```

| Layer | Source file | When it fires |
|---|---|---|
| **Seed** | `webagentbench/injector/seed.py` | Once, at session creation, before the agent sees the page. |
| **Server** | `webagentbench/injector/server.py` | Once, after seed, before the first response. |
| **Network** | `webagentbench/injector/middleware.py` | Per HTTP request, on real Pythonic FastAPI middleware. |
| **Client** | `webagentbench/environments/shared/src/components/BenchmarkToolbar.tsx` | Per DOM interaction, registered on browser load. |

---

## 5. Worked Example: A Patience Intervention

A `delay`/`error_then_success` variant on a Gmail "star this email" task.

### Setup phase

1. Agent harness loads `gmail_star_email__transient_503.yaml` (`DegradationConfig.from_yaml(...)`).
2. Harness POSTs `/session` with `{task_id, seed, variant_filename}` to FastAPI.
3. FastAPI calls `seed.apply_seed_injection(state, params)` and `server.apply_server_injection(state, params)`. (No-ops for this variant, but the dispatch order is fixed.)
4. FastAPI calls `register_session_degradation(session_id, injections)`, registering the network-layer dispatch.

### Runtime phase

5. Agent observes the inbox and emits `click("75")` to star a specific email.
6. SPA issues `POST /api/env/gmail/emails/email_3/star`.
7. **Middleware intercepts:**
   - extracts `session_id` from headers,
   - matches the URL pattern,
   - increments call counter (`call_count <= 2`),
   - returns **HTTP 503** with `{"error": "...retry..."}`.
8. The error reaches the SPA. The DOM does not show the star (write was rejected).
9. Agent reads the observation. The star didn't appear.

### Two possible agent behaviours

**Patient agent.** Re-reads observation, recognizes 503 implies "retry," waits a moment, sends `click("75")` again. Third call passes through, write succeeds, star appears.

**Impatient agent.** Treats the missing star as task completion, sends `done("Done")`. No retry.

### Evaluate phase

10. Harness calls `POST /evaluate`.
11. Evaluator reads live `GmailState`. `email.is_starred == False` for the impatient agent.
12. Score: `0.0`. Failure: `missing_update` on the email's `is_starred` field.

> **Ground truth stays independent of the UI.** The middleware returns a real HTTP 503, not a Playwright mock; the same 503 reaches a human browser. A patient agent retries and succeeds; an impatient agent sends "Done" and scores zero. The evaluator asks the live `GmailState` whether the email is starred, so a silently-dropped write is caught regardless of what the DOM shows.

---

## 6. Catalog Map: 29 Families across 4 Layers

### Tasks and Variants per Environment

| Environment | Domain | Base Tasks | Variants | Adversarial-content surface |
|---|---|---|---|---|
| Gmail | Email | 84 | 94 | Email body and sender display name |
| Amazon | E-commerce | 84 | 91 | Product titles, descriptions, reviews |
| Reddit | Social | 81 | 81 | Posts, comments, sub names |
| Robinhood | Finance | 67 | 71 | News headlines, alerts |
| Booking | Travel | 78 | 78 | Property reviews |
| LMS | Education | 65 | 65 | Announcements and discussion posts |
| Patient Portal | Healthcare | 70 | 71 | Clinical messages |
| **Total** | 7 domains | **519** | **530** | — |

### Intervention Families by Layer

| Layer | Families | Dispatch branches | Primary primitives targeted |
|---|---|---|---|
| Seed | 7 | 14 | grounding, state tracking, exploration, backtracking, verification |
| Server | 5 | 10 | planning, state tracking, grounding, exploration, verification |
| Network | 7 | 8 | patience, verification, backtracking, state tracking |
| Client | 10 | 16 | grounding, verification, exploration, backtracking, patience |
| **Total** | **29** | **48** | all seven primitives |

### Seed Families · `injector/seed.py`

| Family | What it does | Dispatches | Primitives |
|---|---|---|---|
| Decoys & aliases | Inserts near-identical items or similarly-named entities into the target list to dilute the signal the agent must ground to. | `add_confusing_decoys`, `alias_entities`, `increase_distractors`, `add_decoy_notifications`, `add_noise_orders`, `add_confusing_positions`, `add_confusing_stocks` | grounding |
| Adversarial content | Plants hostile items (phishing, prompt injection, urgency, impersonation, authority appeal). Paired with negative checks that fire if the agent follows the injected instruction. | `inject_adversarial_content`, `add_misleading_alert` | grounding, verification |
| Split information | Distributes task-critical information across multiple items so the agent cannot resolve the task from any single one. | `split_information` | state tracking |
| Contradictory update | Inserts a newer item that contradicts an older one. The agent must reconcile to the newer value. | `add_contradictory_update` | state tracking |
| Content inflation | Pads the target body with realistic filler (threads, legal boilerplate, digests); the answer is preserved at a chosen position (early / middle / late / repeated_contradicted). | `inflate_target_content` | state tracking, exploration |
| Planted wrong answer | Places a plausible-but-incorrect answer first, so a greedy agent commits to it without continuing to search. | `plant_wrong_answer` | backtracking |
| Hidden target | Buries the target item in an atypical folder, archive, or tab. | `hide_in_non_obvious_location` | exploration |

### Server Families · `injector/server.py`

| Family | What it does | Dispatches | Primitives |
|---|---|---|---|
| Timestamp scramble | Applies random offsets to timestamps within the scope. The apparent chronology no longer matches causal order. | `scramble_timestamps`, `scramble_order_timestamps`, `scramble_notification_timestamps` | planning |
| Ordering shuffle | Randomises list ordering so visual position is uninformative; the agent must re-derive ordering from semantic fields. | `shuffle_contacts`, `shuffle_positions` | state tracking |
| Distractor injection | Adds realistic-looking but irrelevant entries inline with real ones. | `inject_distractor_emails`, `inject_distractor_notifications` | grounding |
| Prerequisite hiding | Removes a label or list that the task description assumes already exists. The agent must create the prerequisite or find a workaround. | `hide_prerequisite`, `hide_watchlist` | exploration |
| Field corruption | Modifies a specific field to introduce an inconsistency the agent must notice and repair on readback. | `corrupt_state` | verification |

### Network Families · `injector/middleware.py`

| Family | What it does | Dispatches | Primitives |
|---|---|---|---|
| Latency | Inserts delay before forwarding to the real handler. Behaviour modes: `once`, `intermittent`, `progressive`, `tail_latency` (piecewise-linear p50/p95/p99), `correlated_window`, `write_only_slow`. | `delay` | patience |
| Transient error | Returns 503 / 500 / 502 / 429 for the first N calls, then passes through. Sets `Retry-After` on 429. | `error_then_success` | backtracking, patience |
| Fabricated success | Returns 200 while the real write is silently dropped. Two variants: `silent_fail` (quiet body) and `misleading_success` (loud body with `success:true, toast:"Saved"`). | `silent_fail`, `misleading_success` | verification |
| Stale response | Returns outdated or empty body for the first N GETs. The agent must reconcile a read that does not reflect a prior write. | `stale_data` | state tracking |
| Optimistic conflict | Returns 409 Conflict with a `latest_snapshot` of the "newer" state. The agent must reload and reconcile before retrying. | `concurrent_modification` | backtracking |
| Rate limit | After `burst_limit` calls, returns 429 with `Retry-After` for the next `cooldown_calls` requests. Tests whether the agent reads structured error responses. | `rate_limit` | patience |
| Session expiry | After `expire_after_calls`, returns 401. Cleared by a request to `reauth_path`. | `session_expiry` | backtracking |

### Client Families · `BenchmarkToolbar.tsx`

| Family | What it does | Dispatches | Primitives |
|---|---|---|---|
| Label misbinding | Shifts or rotates accessibility associations (`aria-label`, `<label for>`, visible text) so agents relying on DOM semantics pick the wrong element. | `scramble_aria`, `swap_labels`, `label_input_misalignment` | grounding |
| Decoy element | Clones a clickable element and strips its handler, inserted adjacent to the real control. | `add_decoy` | grounding |
| Hidden/restricted affordance | Hides the default entry point or disables all but one of a row's redundant controls (image / title / menu / primary button). | `hide_affordance`, `restrict_affordance_set` | exploration, backtracking |
| Deceptive banner | Injects a misleading alert banner above the page content. | `false_banner` | grounding, verification |
| Swallowed click | First N clicks on a matching selector are no-ops; subsequent clicks work normally. | `click_swallow` | verification, patience |
| Input perturbation | Corrupts what the user typed or selected before it leaves the browser: neighbour-swap on `<select>` / date / radio, character-level corruption, or single-field drift at submit. | `adjacent_selection`, `input_corruption`, `save_drift` | verification |
| Double-fire trap | A second click on a submit-style button within `window_ms` fires the action twice. | `double_submit_trap` | verification, patience |
| Intercepting overlay | Near-invisible overlay (opacity 0.02) swallows clicks over a region. Dismissed by Escape or an 18×18-px corner button. | `intercepting_overlay` | exploration, patience |
| Stuck loader | Loading skeleton on a specific route never resolves; only refresh or navigation clears it. | `skeleton_never_resolves` | backtracking, patience |
| Interrupting modal | Injects a cookie / newsletter / survey modal on the Nth navigation. Close control is deliberately small (12 px); Escape dismisses. | `distractor_modal` | grounding, patience |

> One infrastructure branch, `set_feature_flag`, is excluded from family / dispatch counts: it toggles a `window.__wabFeatureFlags` boolean and imposes no cognitive load on its own.

### Primitive Coverage Across Environments

Every primitive has at least one variant in every environment. This lets a user compute a primitive-by-environment score matrix from a single evaluation run.

| | Gmail | Amazon | Reddit | Robinhood | Booking | LMS | Portal |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Grounding | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Planning | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| State Tracking | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Backtracking | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Patience | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Exploration | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Verification | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 7. Design Invariants

Every variant in the catalog satisfies all five invariants. They are the contract that makes scoring meaningful.

| Invariant | Meaning |
|---|---|
| **Deterministic** | Every action takes a seed. The same variant produces the same degradation trajectory across runs. |
| **Detectable** | An attentive agent can notice the degradation: the degraded element stays visible in the DOM, the response body carries the HTTP status, and a form readback reveals corrupted values. |
| **Recoverable** | A competent agent can work around the degradation with a bounded number of extra actions. Interventions filter capability; they do not block it. |
| **Primitive-pure** | One target primitive per variant. Any task with a secondary primitive is narrowed when a variant's target lies outside the task's existing set. |
| **Realistic** | Every action corresponds to a real-world failure class: slow network, expired session, phishing email, broken layout, rate limit, 409 conflict. |

---

## 8. Evaluation System

Scoring runs against **live environment state** rather than the DOM. The evaluator reads the Pydantic state objects the real API handlers mutate, so a silently-dropped write is caught even when the UI shows a success toast. Every task declares a `canonical_diff` block, and matching runs through `webagentbench/eval_core/`. (The legacy expression-based `eval.checks` path was removed in the 2026-04 refactor; all 519 tasks now carry a `canonical_diff`.)

### Pipeline

```python
# webagentbench/eval_core/orchestrator.py
def evaluate(task, server_state, targets, trajectory):
    canonical = task.canonical_diff              # missing_canonical_diff → score 0
    initial   = server_state._initial_state_copy  # deep-copy taken at session create

    agent_diff = compute_diff(initial, server_state)   # eval_core/diff.py
    report     = match_diff(agent_diff, canonical,     # eval_core/matcher.py
                            targets, initial, server_state, session_start)

    return {
        "score":            report.score,
        "success":          report.passed,
        "checks":           report.checks,             # positive match results
        "negative_checks":  report.negative_checks,    # invariants + constraints + collateral
        "failures":         report.failures,
        "collateral":       state.compute_collateral(initial),  # analytics only
        "bijection_graphs": report.bijection_graphs,
    }
```

### Five Grammar Sections of `canonical_diff`

| Section | Role | Contributes to score via |
|---|---|---|
| `create` | Entities the agent must bring into existence (e.g. new `CartItem`, new `Message`). | Weighted positive match; bijection from expected entities to actual diff entries. |
| `update` | Existing entities whose fields must change in specified ways. | Weighted positive match against `UpdateEntry.changes`. |
| `delete` | Entities the agent must remove. | Weighted positive match against observed `DeleteEntry`s. |
| `invariant` | Collections that must be preserved. Optional `filter` narrows scope (e.g. every cart item *except* the target). A matching unmatched diff entry is a violation. | Negative check (medium penalty by default). |
| `constraints` | Global predicates over final state (read-only). Carry their own `severity`. | Negative check, or the sole positive term if no create/update/delete exists. |

Two auxiliary structures extend the grammar: `oneof` wraps multiple acceptable alternatives at the block level and the matcher picks the best-scoring applicable alternative; `named_invariants` attach human-readable names and severities (`critical` / `high` / `medium` / `low`) to the invariant list.

### Example `canonical_diff` — abridged from `amazon_add_single_item.yaml`

```yaml
canonical_diff:
  create:
  - entity: CartItem
    desc: Target product added to cart with quantity 1
    properties:
      product_id: {expr: "x == target['product_id']"}
      quantity:   {eq: 1}
      product_name: {any: true}
  invariant:
  - collection: state.cart_items
    filter: "a.product_id != target['product_id']"   # preserve everything but the target
    preserve: ALL
  named_invariants:
  - {name: Agent did not place orders, ref: invariant[4], severity: high}
```

### Predicate Grammar (19 keys) · `eval_core/predicates.py`

Properties of a create/update are matched by predicates, each a single-key mapping.

| Category | Predicates |
|---|---|
| Scalar | `eq`, `in`, `between`, `any` |
| Collection | `set_eq`, `subset`, `superset`, `contains`, `length` |
| Text | `substring`, `substring_all`, `substring_any`, `regex`, `matches_semantic` (difflib ratio, default threshold 0.8) |
| Structural | `fields` (nested dict predicate) |
| Boolean | `not`, `all_of`, `any_of` |
| Expression | `expr`: restricted Python. Bindings: `x` (current value), `v` (bijection variable), `target`, `initial`, `state`, `session_start`. Allowlist-guarded via `eval_core/safe_eval.py`. |

### Automatic Collateral Sweep

After matching the explicit sections, the matcher scans every unmatched diff entry and penalises the agent for uncovered state mutations:

| Situation | Penalty |
|---|---|
| Mutation in a collection the task cares about (mentioned by create/update/delete) but not covered by any matched entry or invariant. | `medium` (0.15), labelled *Unaccounted &lt;kind&gt; in &lt;collection&gt;* |
| Mutation in a collection the task does not mention at all. | `high` (0.20), labelled *Unexpected &lt;kind&gt; on &lt;collection&gt;* |
| Inside a `filter`ed invariant marked `comprehensive: true`. | suppressed (filter is treated as covering the whole collection). |

The agent is not required to enumerate every side-effect explicitly; a collection-level invariant blocks the sweep. The sweep exists to catch overreach: a successful "add to cart" that also silently writes a review or cancels an order loses score.

### Score Formula · `eval_core/matcher.py`

Severity table: `critical` 0.30, `high` 0.20, `medium` 0.15, `low` 0.10.

```python
if total_weight > 0:                  # create/update/delete present
    raw_score = passed_weight / total_weight
elif constraints_total:               # constraint-only task
    raw_score = constraints_passed / constraints_total
else:
    raw_score = 1.0

penalty_total = sum(nc.penalty for nc in negative_checks if not nc.passed)
score         = max(0.0, min(1.0, raw_score - penalty_total))
success       = not failures      # any hard failure → not success
```

> **Why server state.** The DOM is manipulated by client-layer interventions, but `state.emails[]` and `state.cart_items[]` mutate only through real API handlers. A silently-failed star earns no credit because the evaluator reads the live `GmailState`, not the rendered page. An agent that adds the right cart item but also silently triggers a purchase loses score because the collateral sweep flags the unaccounted order.

---

## 9. Evaluated Agents

We evaluate eight frontier models under two action surfaces: a **vision** harness (BrowserGym observations, screenshot plus accessibility tree) and a **text** harness (Browser Use, DOM-structured text actions). The same variant and seed is used for both surfaces, so the cross-surface gap isolates the contribution of visual grounding.

| | Qwen3-VL 235B A22B | Kimi 2.5 | Sonnet 4.6 | Opus 4.7 | Gemini 3 Flash | Gemini 3.1 Pro | GPT 5.4 mini | GPT 5.4 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Vision (BrowserGym) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Text (Browser Use) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

All models are called through their chat API. The vision and text harnesses differ only in how observations are presented and which action verbs are available; the variant catalog, seeding, and evaluator are identical.

---

## 10. Human Baseline

Human trajectories serve two distinct purposes. We collect both on every task, across both the baseline and the intervened versions.

### Cold-Start Baseline

A participant sees the task for the first time and completes it without prior exposure to the environment. We record **pass rate** (did the task succeed under the scoring rubric) and **completion time**. This is the human headroom reference: the gap between cold-start human accuracy and frontier-agent accuracy quantifies the capability deficit on each primitive.

### Optimal Trajectory

A proficient participant who already knows the environment completes the task along the shortest sensible path. We record the action sequence and its length. This trajectory is the **efficiency reference**: an agent's step count is compared against the optimal trajectory to produce an efficiency ratio independent of raw success.

### How the Two Baselines Combine

| Metric | Human signal | What it tells us about agents |
|---|---|---|
| Success rate | Cold-start pass rate | Capability ceiling: how much of the task distribution is humanly solvable at all. |
| Primitive delta | Cold-start pass rate on baseline vs. intervention | How much each primitive costs a fresh human — and therefore how much of any agent drop is attributable to the intervention rather than task difficulty. |
| Efficiency | Optimal trajectory step count | Agent step count divided by optimal step count gives a normalized efficiency score; successful but inflated agent runs surface here. |

> **Why both baselines.** Raw human pass rate does not separate "fresh user thinking from scratch" from "expert acting optimally." Cold-start pass rate measures the first; optimal trajectory measures the second. Agents are compared against both: accuracy against cold start, efficiency against optimal.

---

## 11. Environments

Seven fully interactive web environments, each a faithful reproduction of a real-world platform. Each ships a React SPA, a FastAPI backend, Pydantic state models, and YAML-seeded initial data.

| Environment | Domain | Typical task | Why it is in the set |
|---|---|---|---|
| **Gmail** | Email | Find an action item, star a thread, draft a reply. | High-volume daily task; heavy grounding and state-tracking load. |
| **Amazon** | E-commerce | Add-to-cart, modify quantity, check out. | Multi-step commitment flow; verification and grounding under adversarial surfaces. |
| **Reddit** | Social | Post, comment, navigate a thread. | User-generated noise; adversarial content tests. |
| **Robinhood** | Finance | Place or modify an order, check a position, read a notification. | Irreversible actions with real-world analogue; verification under time pressure. |
| **Booking.com** | Travel | Search, filter, reserve a property. | Long filter chains; planning and state tracking. |
| **LMS** | Education | Find a syllabus item, submit an assignment, read an announcement. | Hierarchical navigation; exploration load. |
| **Patient Portal** | Healthcare | Message a provider, schedule a visit, read a lab result. | High-stakes content; verification and grounding against clinical messages. |

---

## 12. Repository Structure

```
webagentbench/
  injector/
    config.py            # DegradationConfig dataclass + default templates
    seed.py              # seed-layer actions
    server.py            # server-layer actions
    middleware.py        # DegradationMiddleware (primary network interception)
    network.py           # Playwright page.route() parity
    apply.py             # orchestrator
    variants/            # 530 YAML variants

  backend/
    models/{env}.py      # Pydantic state shapes
    routes/{env}.py      # REST endpoints + session create/evaluate
    seeders/{env}.py     # YAML → seeded state

  tasks/
    _schema.py           # TaskDefinition, EvalConfig
    _registry.py         # YAML discovery
    _evaluator.py        # restricted-eval checker
    {env}/               # per-env task YAMLs

  environments/
    {env}/               # React SPA per env
    shared/src/components/BenchmarkToolbar.tsx  # client-layer injections

  eval_core/
    orchestrator.py      # evaluate() entry point
    diff.py              # compute_diff()
    matcher.py           # match_diff() + score formula
    predicates.py        # 19 predicate keys
    safe_eval.py         # restricted-Python expression checker
```

---

## 13. Running PrimBench

### Install

```bash
uv sync && uv run playwright install chromium
pnpm -C webagentbench/environments install
./scripts/webagentbench.sh build
```

### Baseline run (no intervention)

```bash
python -m webagentbench.agent_eval \
    --model gpt-4o --provider openai --api-key $KEY \
    --tasks gmail_action_item_extraction \
    --max-steps 50 --seed 42 \
    --output results/baseline.json
```

### Intervention run (same task, one variant)

```bash
python -m webagentbench.agent_eval \
    --model gpt-4o --provider openai --api-key $KEY \
    --tasks gmail_action_item_extraction \
    --degradation gmail_action_item_extraction__phishing_inbox.yaml \
    --max-steps 50 --seed 42 \
    --output results/phishing.json
```

### Visualise any result JSON

```bash
python -m webagentbench.visualize results/phishing.json
```

### Human play (collects cold-start and optimal trajectories)

```bash
python -m webagentbench.app --host 127.0.0.1 --port 8080
# Open http://127.0.0.1:8080/launch
```

### Stock browser-use harness (alternative agent runner)

The repo also ships `webagentbench/stock_browseruse_eval.py`, a second harness built on upstream `browser_use.Agent` with minimal customisation. It runs the same task set with a different agent loop, so readers can separate "model ability" from "harness choice." See `webagentbench/README.md` for the operations runbook.

---

PrimBench · Diagnosing Cognitive Primitives of Web Agents via Environment Interventions
