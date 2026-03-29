"""
Generate LLMOS Gmail templates from the canonical WebAgentBench task pipeline.

This script is an exporter only:
- task definitions come from the YAML registry
- seeded state comes from the shared task materializer
- rendered instructions come from the shared template renderer

Usage:
    python scripts/generate_gmail_templates.py
    python scripts/generate_gmail_templates.py --tasks gmail_thread_detective
    python scripts/generate_gmail_templates.py --only-new
    python scripts/generate_gmail_templates.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webagentbench.backend.models.gmail import GmailState
from webagentbench.task_materialization import MaterializedTask, materialize_task
from webagentbench.tasks._registry import env_tasks


PAGE_SIZE = 16  # matches the React Inbox component


def load_gmail_tasks() -> dict[str, object]:
    return {task.task_id: task for task in env_tasks("gmail")}


def make_bid(role: str, name: str, counter: list[int]) -> str:
    counter[0] += 1
    if name:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())[:40].rstrip("_")
        return f"{role}_{safe}_{counter[0]}"
    return f"{role}_{counter[0]}"


def _node(bid: str, tag: str, role: str, text: str = "", **kwargs) -> dict:
    node = {
        "bid": bid,
        "tag": tag,
        "role": role,
        "text": text,
        "visible": True,
        "bounds": {"x": 0, "y": 0, "width": 800, "height": 30},
    }
    node.update(kwargs)
    return node


def format_timestamp(ts: datetime) -> str:
    return ts.strftime("%b %d")


def gmail_state_to_ui(state: GmailState) -> dict:
    """Convert canonical Gmail state into the LLMOS UI tree format."""
    counter = [0]

    def bid(role: str, name: str = "") -> str:
        return make_bid(role, name, counter)

    emails = state.emails

    def _category_of(email) -> str:
        if "promotions" in email.labels:
            return "promotions"
        if "updates" in email.labels:
            return "updates"
        return "primary"

    inbox_emails = [
        email
        for email in emails
        if "inbox" in email.labels and not email.archived and not email.deleted
    ]
    primary_emails = [email for email in inbox_emails if _category_of(email) == "primary"]

    display_emails = primary_emails
    total = len(display_emails)
    page_emails = display_emails[:PAGE_SIZE]
    range_end = min(PAGE_SIZE, total)
    inbox_count = len(inbox_emails)

    topbar = _node(
        bid("banner", "Gmail"),
        "header",
        "banner",
        "Gmail",
        children=[
            _node(bid("text", "Gmail"), "span", "text", "Gmail"),
            _node(bid("searchbox", "Search mail"), "input", "searchbox", "Search mail"),
        ],
    )

    sidebar = _node(
        bid("navigation", "Gmail navigation"),
        "nav",
        "navigation",
        "Gmail navigation",
        children=[
            _node(bid("button", "Compose"), "button", "button", "Compose"),
            _node(bid("link", "Inbox"), "a", "link", f"Inbox ({inbox_count})"),
            _node(bid("link", "Starred"), "a", "link", "Starred"),
            _node(bid("link", "Sent"), "a", "link", "Sent"),
            _node(bid("link", "Drafts"), "a", "link", "Drafts"),
            _node(bid("link", "Archive"), "a", "link", "Archive"),
            _node(bid("link", "Trash"), "a", "link", "Trash"),
            _node(bid("link", "Settings"), "a", "link", "Settings"),
            _node(bid("link", "Labels"), "a", "link", "Labels"),
        ],
    )

    tabs = [
        _node(bid("tab", "Primary"), "button", "tab", "Primary", selected=True),
        _node(bid("tab", "Promotions"), "button", "tab", "Promotions"),
        _node(bid("tab", "Updates"), "button", "tab", "Updates"),
        _node(bid("tab", "All Mail"), "button", "tab", "All Mail"),
    ]

    email_rows = []
    for email in page_emails:
        star_label = (
            f"Unstar {email.subject}" if email.is_starred else f"Star {email.subject}"
        )
        snippet = " ".join(email.body.split())[:140]
        row = _node(
            bid("article", email.subject),
            "article",
            "article",
            "",
            children=[
                _node(bid("button", star_label), "button", "button", star_label),
                _node(bid("text", email.from_name), "span", "text", email.from_name),
                _node(
                    bid("link", f"Open thread {email.subject}"),
                    "a",
                    "link",
                    f"Open thread {email.subject}",
                    children=[
                        _node(bid("text", email.subject), "span", "text", email.subject),
                        _node(bid("text", snippet), "span", "text", snippet),
                    ],
                ),
                _node(
                    bid("button", f"Archive {email.subject}"),
                    "button",
                    "button",
                    f"Archive {email.subject}",
                ),
                _node(
                    bid("button", f"Delete {email.subject}"),
                    "button",
                    "button",
                    f"Delete {email.subject}",
                ),
                _node(
                    bid("text", format_timestamp(email.timestamp)),
                    "span",
                    "text",
                    format_timestamp(email.timestamp),
                ),
            ],
        )
        email_rows.append(row)

    pagination = []
    if total > 0:
        pagination.append(
            _node(
                bid("text", f"1–{range_end} of {total}"),
                "span",
                "text",
                f"1–{range_end} of {total}",
            )
        )
        pagination.append(
            _node(
                bid("button", "Previous page"),
                "button",
                "button",
                "Previous page",
                disabled=True,
            )
        )
        pagination.append(
            _node(
                bid("button", "Next page"),
                "button",
                "button",
                "Next page",
                **({"disabled": True} if total <= PAGE_SIZE else {}),
            )
        )

    main_content = _node(
        bid("main", "Inbox"),
        "main",
        "main",
        "Inbox",
        children=tabs + email_rows + pagination,
    )

    page_content = _node(
        "page_content",
        "main",
        "main",
        "Gmail",
        children=[topbar, sidebar, main_content],
    )
    return _node(
        "root",
        "browser",
        "application",
        "Gmail",
        children=[
            _node(
                "toolbar",
                "toolbar",
                "toolbar",
                "Browser Toolbar",
                children=[
                    _node(
                        "url_bar",
                        "input",
                        "textbox",
                        "Address",
                        value="https://webagentbench.local/env/gmail/inbox",
                    ),
                ],
            ),
            page_content,
        ],
    )


def build_gmail_template(materialized: MaterializedTask) -> dict:
    ui = gmail_state_to_ui(materialized.state)

    hidden_state = {
        "wab_page_id": materialized.task.task_id,
        "wab_instruction": materialized.instruction,
        "task_completion_criteria": materialized.resolved_targets,
    }

    return {
        "meta": {
            "tick": 0,
            "status": "running",
            "random_seed": materialized.seed,
            "platform": "webagentbench",
            "task_category": materialized.task.task_id,
            "target_primitives": materialized.task.primary_primitives,
        },
        "hidden_state": hidden_state,
        "ui": ui,
        "filesystem": {},
        "tabs": [
            {
                "id": 0,
                "url": "https://webagentbench.local/env/gmail/inbox",
                "title": "Gmail",
                "active": True,
            }
        ],
        "history": [],
    }


def count_nodes(node: dict) -> int:
    count = 1
    for child in node.get("children", []):
        count += count_nodes(child)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate LLMOS templates for Gmail tasks"
    )
    parser.add_argument("--output-dir", type=str, default="llmos/templates")
    parser.add_argument(
        "--tasks", nargs="+", default=None, help="Specific task IDs (default: all)"
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="Only generate tasks without existing templates",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_tasks = load_gmail_tasks()
    task_ids = args.tasks or list(all_tasks.keys())

    if args.only_new:
        task_ids = [task_id for task_id in task_ids if not (output_dir / f"{task_id}.json").exists()]

    generated = 0
    errors = 0

    for task_id in task_ids:
        task = all_tasks.get(task_id)
        if task is None:
            print(f"[{task_id}] SKIP: no Gmail task definition found")
            continue

        try:
            materialized = materialize_task("gmail", task_id, seed=args.seed)
        except Exception as exc:
            print(f"[{task_id}] ERROR: {exc}")
            errors += 1
            continue

        if args.dry_run:
            inbox = [
                email
                for email in materialized.state.emails
                if "inbox" in email.labels and not email.archived
            ]
            print(
                f"[{task_id}] emails={len(materialized.state.emails)} "
                f"inbox={len(inbox)} "
                f"targets={list(materialized.resolved_targets.keys())[:4]}..."
            )
            generated += 1
            continue

        template = build_gmail_template(materialized)
        out_path = output_dir / f"{task_id}.json"
        out_path.write_text(json.dumps(template, indent=2, default=str) + "\n")

        inbox_count = sum(
            1
            for email in materialized.state.emails
            if "inbox" in email.labels and not email.archived
        )
        print(
            f"[{task_id}] -> {out_path} "
            f"({count_nodes(template['ui'])} nodes, {inbox_count} inbox emails)"
        )
        generated += 1

    mode = "Checked" if args.dry_run else "Generated"
    print(f"\n{mode} {generated} templates, {errors} errors")


if __name__ == "__main__":
    main()
