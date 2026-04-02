"""Server injection layer: feature flags applied to environment state.

Targets Planning, State Tracking, and Backtracking primitives.
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any


def apply_server_injection(state: Any, params: dict[str, Any]) -> None:
    """Mutate server state to create degraded conditions."""
    action = params.get("action", "")
    mutated = False

    if action == "scramble_timestamps":
        rng = random.Random(params.get("seed", 42))
        if hasattr(state, "emails"):
            for email in state.emails:
                if hasattr(email, "timestamp"):
                    offset = rng.randint(-86400 * 7, 86400 * 7)
                    email.timestamp += timedelta(seconds=offset)
                    mutated = True

    elif action == "shuffle_contacts":
        rng = random.Random(params.get("seed", 42))
        if hasattr(state, "contacts"):
            rng.shuffle(state.contacts)
            mutated = True

    elif action == "hide_prerequisite":
        label_name = params.get("label_name")
        if label_name and hasattr(state, "labels"):
            state.labels = [lab for lab in state.labels if lab.name != label_name]
            mutated = True

    elif action == "inject_distractor_emails":
        count = params.get("count", 5)
        subject_prefix = params.get("subject_prefix", "")
        if hasattr(state, "emails") and state.emails:
            _REALISTIC_EMAILS = [
                {
                    "subject": "Quick follow-up on our earlier discussion",
                    "body": "Hey, just wanted to circle back on what we talked about this morning. I think we're aligned on the timeline but I want to double-check the resource allocation before I update the tracker. Can you confirm whether the Q3 numbers are final?",
                },
                {
                    "subject": "Updated timeline for the deliverables",
                    "body": "Hi team,\n\nI've pushed the design review to Thursday based on the feedback from stakeholders. Engineering milestones stay the same. Please flag any conflicts by EOD tomorrow so we can adjust.",
                },
                {
                    "subject": "Notes from today's sync",
                    "body": "Sharing notes from the sync:\n\n1. Dashboard redesign approved — dev starts next sprint\n2. API migration blocked on the auth team's review\n3. Hiring update: two offers out, one accepted\n\nLet me know if I missed anything.",
                },
                {
                    "subject": "Revised figures — please review",
                    "body": "Attached the updated projections with the corrected assumptions. Main change: we moved the infrastructure costs from OpEx to CapEx per finance's guidance. Net impact is about $40K lower quarterly burn.",
                },
                {
                    "subject": "Re: Action items from the meeting",
                    "body": "Following up on the three open items:\n\n- Contract review: legal says they need until Friday\n- Vendor selection: narrowed to two finalists, scheduling demos\n- Budget reallocation: waiting on director approval\n\nI'll send another update once legal comes back.",
                },
                {
                    "subject": "One more thing on the project scope",
                    "body": "I realized we didn't address the internationalization requirement in today's planning. If we're targeting EU launch in Q2, we need to budget for translation and compliance review. Adding it to the backlog for now.",
                },
                {
                    "subject": "Sharing the latest draft for your feedback",
                    "body": "Here's the v3 draft incorporating the comments from last round. I restructured section 2 and added the competitive analysis appendix. Would appreciate your review by Wednesday so we can finalize before the board presentation.",
                },
                {
                    "subject": "Heads up on the schedule change",
                    "body": "The all-hands got moved from Tuesday 3pm to Wednesday 10am due to a conflict with the leadership offsite. Same agenda, same Zoom link. Calendar invites updated.",
                },
                {
                    "subject": "Checking in on the open items",
                    "body": "Haven't heard back on the two items from last week — the vendor NDA and the staging environment access request. Are these still blocked or did they get resolved? Happy to help push things along if needed.",
                },
                {
                    "subject": "Summary of decisions from this morning",
                    "body": "Quick recap of what we decided:\n\n- Go with Option B for the pricing model\n- Delay the beta launch by two weeks to fix the onboarding flow\n- Hire a contractor for the data migration piece\n\nI'll update the project plan and share it by EOD.",
                },
            ]
            _REALISTIC_NAMES = [
                ("Jordan Park", "jordan.park@company.test"),
                ("Morgan Liu", "morgan.liu@company.test"),
                ("Casey Rivera", "casey.rivera@company.test"),
                ("Taylor Brooks", "taylor.brooks@company.test"),
                ("Riley Santos", "riley.santos@company.test"),
                ("Quinn Patel", "quinn.patel@company.test"),
                ("Drew Nakamura", "drew.nakamura@company.test"),
                ("Jamie Okafor", "jamie.okafor@company.test"),
                ("Alex Drummond", "alex.drummond@company.test"),
                ("Avery Kim", "avery.kim@company.test"),
            ]
            rng = random.Random(params.get("seed", 42))
            template = state.emails[0]
            for i in range(count):
                distractor = template.model_copy(deep=True)
                distractor.id = f"email_{rng.randint(10000, 99999)}"
                distractor.thread_id = f"thread_{rng.randint(10000, 99999)}"
                entry = _REALISTIC_EMAILS[i % len(_REALISTIC_EMAILS)]
                distractor.subject = f"{subject_prefix}{entry['subject']}"
                name, addr = _REALISTIC_NAMES[i % len(_REALISTIC_NAMES)]
                distractor.from_name = name
                distractor.from_addr = addr
                distractor.body = entry["body"]
                distractor.is_read = rng.random() > 0.4  # 60% read, 40% unread
                offset = rng.randint(-3600 * 48, 3600 * 2)
                distractor.timestamp += timedelta(seconds=offset)
                state.emails.insert(rng.randint(0, len(state.emails)), distractor)
                mutated = True

    elif action == "corrupt_state":
        # Modify an email field to create inconsistency agent must detect
        email_id = params.get("email_id")
        field = params.get("field", "subject")
        new_value = params.get("value", "CORRUPTED")
        if email_id and hasattr(state, "emails"):
            for email in state.emails:
                if email.id == email_id:
                    setattr(email, field, new_value)
                    mutated = True
                    break

    if mutated and hasattr(state, "touch"):
        state.touch()
