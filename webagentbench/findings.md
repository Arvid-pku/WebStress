# Findings & Decisions

## Requirements
- Read and check the Amazon environment and related benchmark.
- Look for bugs and design issues.
- Browser automation is allowed where it helps validate behavior.

## Research Findings
- The Amazon implementation spans backend model/route/seeder files, a dedicated frontend under `environments/amazon`, task YAMLs under `tasks/amazon`, and injector variants under `injector/variants`.
- The git worktree already contains a large uncommitted Amazon addition; the review treats that local state as the artifact under audit.
- Amazon frontend typecheck currently fails in `ProductDetail.tsx` because the UI expects `ProductVariant.id`, but the model/type only exposes `{name, value, price_modifier, in_stock}`.
- Direct session creation over all Amazon tasks found 12 of 40 tasks fail before runtime due to seed-output alias mismatches.
- Direct evaluator sweeps found at least 5 Amazon tasks whose checks error immediately on untouched seeded state because task YAMLs refer to wrong fields or unsupported builtins.
- Direct route execution confirmed backend/frontend contract drift: wishlist/account/payment/returns/cart/promo responses do not match the frontend API/types layer.
- Direct route execution confirmed `/promo/apply` increments promo usage but does not set `state.applied_promo_code`, so cart totals remain unchanged after promo application.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Use planning files for the audit | The task requires many inspection and validation steps |
| Review backend and benchmark definitions before broad UI exploration | State/model defects explain benchmark breakage more directly than UI symptoms |
| Validate by calling route functions directly | This avoided blocked local-server/browser setup while still exercising real state transitions |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Repo contains existing uncommitted changes unrelated to this turn | Avoid implementation edits and focus on audit/reporting |
| `TestClient` unavailable because local venv lacks `httpx` | Switched to direct route-function validation |
| Local port binding denied in sandbox | Did not request escalation because direct validation was sufficient for the audit |

## Resources
- `backend/models/amazon.py`
- `backend/routes/amazon.py`
- `backend/seeders/amazon.py`
- `environments/amazon/src`
- `tasks/amazon`
- `injector/variants`
- `tests/test_benchmark_integrity.py`

## Visual/Browser Findings
- Browser automation was prepared but not used for final validation because sandbox-local server binding was denied and the route/model probes already exposed benchmark-blocking defects.
