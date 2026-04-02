#!/usr/bin/env python3
"""
Robinhood task debugger — observe, act, verify.

Observe (browser):  screenshot + a11y tree of any page
Act (API):          place orders, set alerts, create watchlists, etc.
Verify (API):       run eval checks, dump server state

Usage:
  python rh_debug.py start <task_id> [--seed N]   Create session, screenshot home
  python rh_debug.py see [path]                    Screenshot + a11y tree (default: current page)
  python rh_debug.py act <endpoint> <json>         POST to API endpoint
  python rh_debug.py state                         Dump all server state
  python rh_debug.py check                         Run eval checks
  python rh_debug.py batch <task_id> [task_id...]   Quick-test: create session + check for each
  python rh_debug.py batch --all                   Quick-test all 65 tasks
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = os.environ.get("WAB_URL", "http://127.0.0.1:8080")
API = f"{BASE}/api/env/robinhood"
DIR = Path("scripts/debug_screenshots")
SF = Path("scripts/.rh_session.json")


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

def _get(path, sid=None):
    r = httpx.get(f"{API}/{path}", params={"session_id": sid or _sid()}, timeout=30)
    r.raise_for_status()
    return r.json()

def _post(path, payload):
    r = httpx.post(f"{API}/{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def _unwrap(data):
    """Unwrap {items: [...]} → [...]"""
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
    """Compact dump of all server state."""
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
    for label, ep in sections:
        try:
            data = _unwrap(_get(ep, sid))
        except Exception:
            continue

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

def batch(task_ids):
    """Quick-test: create session + run checks for each task. Reports errors."""
    import yaml

    if not task_ids or task_ids == ["--all"]:
        task_dir = Path("webagentbench/tasks/robinhood")
        task_ids = []
        for f in sorted(task_dir.glob("*.yaml")):
            if f.name.startswith("_"):
                continue
            data = yaml.safe_load(f.read_text())
            task_ids.append(data["task_id"])

    results = []
    for i, tid in enumerate(task_ids):
        label = f"[{i+1}/{len(task_ids)}] {tid}"
        try:
            resp = _post("session", {"task_id": tid, "seed": 42})
            sid = resp["session_id"]
            _save({"session_id": sid, "task_id": tid, "instruction": resp["instruction"],
                    "start_path": resp.get("start_path", "/"), "current_path": "/", "seed": 42})

            ev = _post("evaluate", {"session_id": sid, "task_id": tid})
            checks = ev.get("check_results", ev.get("checks", []))
            errored = [c for c in checks if c.get("error")]
            vacuous = [c for c in checks if c.get("passed") and "all(" in c.get("expr", "")]

            score = ev.get("score", 0)
            status = "ERROR" if errored else ("VACUOUS" if score >= 1.0 else "ok")

            if status != "ok":
                print(f"  {label}: {status} score={score:.2f}")
                for c in errored:
                    print(f"    ERR: {c.get('desc')}: {c.get('error')}")
                if score >= 1.0:
                    print(f"    VACUOUS PASS — task passes without any agent action")

            results.append({"task_id": tid, "status": status, "score": score,
                           "errors": [c.get("error") for c in errored]})
        except Exception as e:
            print(f"  {label}: CRASH {e}")
            results.append({"task_id": tid, "status": "crash", "error": str(e)})

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] in ("ERROR", "crash"))
    vac = sum(1 for r in results if r["status"] == "VACUOUS")
    print(f"\n{'='*50}")
    print(f"BATCH: {len(results)} tasks | {ok} ok | {err} errors | {vac} vacuous")
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
    s = sub.add_parser("batch");  s.add_argument("task_ids", nargs="*")

    args = p.parse_args()
    if args.cmd == "start":   start(args.task_id, args.seed)
    elif args.cmd == "see":   see(args.path)
    elif args.cmd == "act":   act(args.endpoint, args.payload)
    elif args.cmd == "state": state()
    elif args.cmd == "check": check()
    elif args.cmd == "batch": batch(args.task_ids or ["--all"])
    else: p.print_help()

if __name__ == "__main__":
    main()
