#!/usr/bin/env python3
"""
Robinhood task debugger — observe, act, verify.

Observe (browser):  screenshot + a11y tree of any page
Act (API):          place orders, set alerts, create watchlists, etc.
Verify (API):       run eval checks, dump server state

Usage:
  python rh_debug.py start <task_id> [--seed N]    Create session, screenshot home
  python rh_debug.py see [path]                     Screenshot + a11y tree
  python rh_debug.py act <endpoint> <json>          POST to API endpoint
  python rh_debug.py state                          Dump all server state
  python rh_debug.py check                          Run eval checks
  python rh_debug.py batch [task_id ...] [-w N]     Parallel quick-test (default: all tasks, 8 workers)
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

BASE = os.environ.get("WAB_URL", "http://127.0.0.1:8080")
API = f"{BASE}/api/env/robinhood"
DIR = Path("scripts/debug_screenshots")
SF = Path(os.environ.get("RH_SESSION_FILE", "scripts/.rh_session.json"))


# ── helpers ──────────────────────────────────────────────────────────────

def _save(d):
    SF.parent.mkdir(parents=True, exist_ok=True)
    SF.write_text(json.dumps(d, indent=2))

def _load():
    return json.loads(SF.read_text()) if SF.exists() else {}

def _sid():
    s = _load()
    if not s:
        sys.exit("No session. Run: rh_debug.py start <task_id>")
    return s["session_id"]

def _client():
    """Shared httpx client with connection pooling."""
    return httpx.Client(base_url=API, timeout=30)

def _get(path, sid=None, client=None):
    c = client or httpx.Client(base_url=API, timeout=30)
    r = c.get(f"/{path}", params={"session_id": sid or _sid()})
    r.raise_for_status()
    if not client:
        c.close()
    return r.json()

def _post(path, payload, client=None):
    c = client or httpx.Client(base_url=API, timeout=30)
    r = c.post(f"/{path}", json=payload)
    r.raise_for_status()
    if not client:
        c.close()
    return r.json()

def _unwrap(data):
    return data["items"] if isinstance(data, dict) and "items" in data else data


# ── observe ──────────────────────────────────────────────────────────────

def see(path=None):
    """Screenshot + a11y tree of a page. Returns tree text."""
    from playwright.sync_api import sync_playwright

    st = _load()
    if not st:
        sys.exit("No session.")

    sid = st["session_id"]
    p = path or st.get("current_path", "/")
    if not p.startswith("/"):
        p = f"/{p}"

    url = f"{BASE}/env/robinhood{p}?session={sid}&agent_mode=1"
    DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=15000)
        time.sleep(1)

        ss = DIR / "_current.png"
        page.screenshot(path=str(ss), full_page=True)

        try:
            tree = page.locator("body").aria_snapshot()
        except Exception:
            tree = "(unavailable)"

        (DIR / "_current_tree.txt").write_text(tree)
        browser.close()

    st["current_path"] = p
    _save(st)

    print(f"PAGE: {p}")
    print(f"SCREENSHOT: {ss}")
    print(f"\nTREE:\n{tree}")
    return tree


# ── act ──────────────────────────────────────────────────────────────────

def act(endpoint, payload_json):
    """POST to an API endpoint with the current session_id injected."""
    payload = json.loads(payload_json)
    payload["session_id"] = _sid()
    result = _post(endpoint, payload)
    print(json.dumps(result, indent=2, default=str))
    return result


# ── state ────────────────────────────────────────────────────────────────

DISPLAY_KEYS = [
    "symbol", "underlying_symbol", "name", "side", "order_type", "quantity",
    "status", "amount", "frequency", "condition", "target_price", "direction",
    "type", "is_read", "strike", "expiration", "option_type", "strategy",
    "two_factor_method", "id",
]

def state():
    """Compact dump of all server state (parallel API calls)."""
    sid = _sid()
    sections = [
        ("Account",       "account"),
        ("Positions",     "positions"),
        ("Orders",        "orders"),
        ("Options",       "options/orders"),
        ("Alerts",        "alerts"),
        ("Watchlists",    "watchlists"),
        ("Recurring",     "recurring"),
        ("Notifications", "notifications"),
        ("Transfers",     "transfers"),
        ("Settings",      "settings"),
    ]

    # Fetch all sections in parallel
    fetched = {}
    with httpx.Client(base_url=API, timeout=30) as client:
        with ThreadPoolExecutor(max_workers=len(sections)) as pool:
            futures = {}
            for label, ep in sections:
                def fetch(ep=ep):
                    r = client.get(f"/{ep}", params={"session_id": sid})
                    r.raise_for_status()
                    return r.json()
                futures[pool.submit(fetch)] = label
            for fut in as_completed(futures):
                label = futures[fut]
                try:
                    fetched[label] = fut.result()
                except Exception:
                    pass

    # Print in original order
    for label, _ in sections:
        data = fetched.get(label)
        if data is None:
            continue
        data = _unwrap(data)
        if isinstance(data, list):
            if not data:
                continue
            print(f"\n{label} ({len(data)})")
            for item in data[:20]:
                parts = [f"{k}={item[k]}" for k in DISPLAY_KEYS if k in item and item[k] is not None]
                print(f"  {' | '.join(parts)}")
        elif isinstance(data, dict):
            vals = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool)) and v not in (None, "", False)}
            if vals:
                print(f"\n{label}")
                for k, v in vals.items():
                    print(f"  {k}: {v}")


# ── check ────────────────────────────────────────────────────────────────

def check():
    """Run eval checks. Returns (score, passed, total, details)."""
    st = _load()
    sid, tid = st["session_id"], st["task_id"]

    resp = _post("evaluate", {"session_id": sid, "task_id": tid})
    score = resp.get("score", 0)
    checks = resp.get("check_results", resp.get("checks", []))

    passed = sum(1 for c in checks if c.get("passed"))
    total = len(checks)

    print(f"\n{'PASS' if resp.get('success') else 'FAIL'}  score={score:.3f}  ({passed}/{total} checks)")
    for c in checks:
        ok = c.get("passed", False)
        print(f"  {'>' if ok else 'X'} {c.get('desc', '?')}")

    return score, passed, total, checks


# ── start ────────────────────────────────────────────────────────────────

def start(task_id, seed=42):
    """Create a session and take initial screenshot."""
    resp = _post("session", {"task_id": task_id, "seed": seed})
    sid = resp["session_id"]

    _save({
        "session_id": sid,
        "task_id": task_id,
        "instruction": resp["instruction"],
        "start_path": resp.get("start_path", "/"),
        "current_path": resp.get("start_path", "/"),
        "seed": seed,
    })

    print(f"SESSION: {sid}")
    print(f"TASK: {resp['instruction']}")

    see()
    return sid


# ── batch ────────────────────────────────────────────────────────────────

def _test_one_task(tid: str, seed: int = 42) -> dict:
    """Test a single task: create session + evaluate. Thread-safe."""
    with httpx.Client(base_url=API, timeout=30) as client:
        try:
            resp = client.post("/session", json={"task_id": tid, "seed": seed}).json()
            if "session_id" not in resp:
                return {"task_id": tid, "status": "crash", "error": str(resp)}
            sid = resp["session_id"]

            ev = client.post("/evaluate", json={"session_id": sid, "task_id": tid}).json()
            checks = ev.get("check_results", ev.get("checks", []))
            errored = [c for c in checks if c.get("error")]
            score = ev.get("score", 0)

            if errored:
                status = "ERROR"
            elif score >= 1.0:
                status = "VACUOUS"
            else:
                status = "ok"

            return {
                "task_id": tid,
                "status": status,
                "score": score,
                "errors": [c.get("error") for c in errored],
            }
        except Exception as e:
            return {"task_id": tid, "status": "crash", "error": str(e)}


def batch(task_ids, workers=8):
    """Parallel quick-test: create session + run checks for each task."""
    import yaml

    if not task_ids:
        task_dir = Path("webagentbench/tasks/robinhood")
        task_ids = []
        for f in sorted(task_dir.glob("*.yaml")):
            if f.name.startswith("_"):
                continue
            data = yaml.safe_load(f.read_text())
            task_ids.append(data["task_id"])

    DIR.mkdir(parents=True, exist_ok=True)
    results = []
    done = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_test_one_task, tid): tid for tid in task_ids}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1

            if r["status"] != "ok":
                print(f"  [{done}/{len(task_ids)}] {r['task_id']}: {r['status']} score={r.get('score', '?')}")
                for err in r.get("errors", []):
                    if err:
                        print(f"    ERR: {err}")
                if r["status"] == "VACUOUS":
                    print(f"    VACUOUS PASS — task passes without any agent action")

    # Sort results to match input order
    order = {tid: i for i, tid in enumerate(task_ids)}
    results.sort(key=lambda r: order.get(r["task_id"], 999))

    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] in ("ERROR", "crash"))
    vac = sum(1 for r in results if r["status"] == "VACUOUS")
    print(f"\n{'='*50}")
    print(f"BATCH: {len(results)} tasks | {ok} ok | {err} errors | {vac} vacuous  [{workers} workers]")
    if err + vac > 0:
        print("\nIssues:")
        for r in results:
            if r["status"] != "ok":
                print(f"  {r['task_id']}: {r['status']}")

    (DIR / "_batch_results.json").write_text(json.dumps(results, indent=2))
    return results


# ── main ─────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Robinhood task debugger")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("start");  s.add_argument("task_id"); s.add_argument("--seed", type=int, default=42)
    s = sub.add_parser("see");    s.add_argument("path", nargs="?")
    s = sub.add_parser("act");    s.add_argument("endpoint"); s.add_argument("payload")
    sub.add_parser("state")
    sub.add_parser("check")
    s = sub.add_parser("batch");  s.add_argument("task_ids", nargs="*"); s.add_argument("-w", "--workers", type=int, default=8)

    args = p.parse_args()
    if args.cmd == "start":   start(args.task_id, args.seed)
    elif args.cmd == "see":   see(args.path)
    elif args.cmd == "act":   act(args.endpoint, args.payload)
    elif args.cmd == "state": state()
    elif args.cmd == "check": check()
    elif args.cmd == "batch": batch(args.task_ids, args.workers)
    else: p.print_help()

if __name__ == "__main__":
    main()
