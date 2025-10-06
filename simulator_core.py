import hashlib
import json
import os
import time
from copy import deepcopy
from typing import Any, Dict, Tuple

from validation import validate_observation, validate_action


def _sha256_digest(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_template(name: str) -> Dict[str, Any]:
    base = os.path.join(os.path.dirname(__file__), "templates", f"{name}.json")
    with open(base, "r", encoding="utf-8") as f:
        return json.load(f)


class SimulatorCore:
    """Deterministic computer environment simulator.

    Maintains private canonical state per episode_id and exposes only agent-visible observations.
    """

    def __init__(self) -> None:
        self._episodes: Dict[str, Dict[str, Any]] = {}

    # ----------------------------- Public API ----------------------------- #
    def reset(self, instruction: Dict[str, Any], seed: int, fidelity: str = "low") -> Tuple[Dict[str, Any], str, str]:
        """Reset environment for a new episode.

        Returns: observation, start_state_digest, episode_id
        """
        template_name = instruction.get("template", "flight_booking")
        template = _load_template(template_name)

        episode_id = f"ep-{seed}-{instruction.get('id','instr')}"

        # Build deterministic initial state
        state: Dict[str, Any] = {
            "seed": int(seed),
            "fidelity": fidelity,
            "template": template_name,
            "windows": [{"id": "win-main", "title": template.get("title", template_name), "focused": True}],
            "page": template.get("page", template_name),
            "ui_elements": self._seed_ui(template, seed),
            "forms": template.get("forms", {}),
            "filesystem": template.get("filesystem", {}),
            "clipboard": "",
            "network_logs": [],
            "processes": ["simulator"],
            "random_seed": int(seed),
        }

        self._episodes[episode_id] = state
        start_digest = _sha256_digest(state)
        obs = self._make_observation(state)
        validate_observation(obs)
        return obs, start_digest, episode_id

    def step(self, episode_id: str, action: Dict[str, Any], timestamp_iso: str, time_delta_ms: int) -> Dict[str, Any]:
        """Apply an atomic action and return the environment transition output.

        Output keys: observation, internal_result, event_log, state_diff, state_digest, terminal, reward_hint
        """
        if episode_id not in self._episodes:
            raise KeyError("Unknown episode_id")

        prev_state = self._episodes[episode_id]
        state = deepcopy(prev_state)

        event_log = []  # internal
        internal_result = {"result": "ok", "reason": ""}
        state_diff: Dict[str, Any] = {}
        terminal = False
        reward_hint = None

        validate_action(action)
        atype = action.get("type")
        target = action.get("target", {})
        element_id = target.get("element_id")
        # Helper to find element
        def find_element(eid: str):
            for el in state["ui_elements"]:
                if el.get("element_id") == eid:
                    return el
            return None

        # Simple rules for flight_booking template
        tmpl = state.get("template")
        if tmpl == "flight_booking":
            if atype == "click" and element_id == "confirm_payment_btn":
                # Determine if form valid
                card_valid = bool(state.get("forms", {}).get("card_valid", False))
                if not card_valid:
                    # Rejected: show error banner + beep
                    internal_result = {"result": "rejected", "reason": "card validation failed"}
                    # Toggle or insert error banner
                    banner = find_element("error_banner")
                    if banner:
                        banner.setdefault("attributes", {})["visible"] = True
                        banner["text"] = "Invalid card number"
                    else:
                        state["ui_elements"].append({
                            "element_id": "error_banner",
                            "role": "banner",
                            "text": "Invalid card number",
                            "attributes": {"visible": True},
                        })
                    # Record event internally
                    event_log.append({
                        "t": timestamp_iso,
                        "event": "rejected",
                        "action": action,
                        "reason": internal_result["reason"],
                    })
                    state_diff["ui_elements"] = ["error_banner"]
                else:
                    # Accepted: simulate ticket creation
                    filename = "/home/user/tickets.pdf"
                    state.setdefault("filesystem", {})[filename] = {
                        "bytes": 128,
                        "kind": "pdf",
                        "created_at": timestamp_iso,
                    }
                    # Update UI with confirmation text
                    confirmation = find_element("confirmation_text")
                    if confirmation:
                        confirmation["text"] = "Booking confirmed"
                        confirmation.setdefault("attributes", {})["visible"] = True
                    else:
                        state["ui_elements"].append({
                            "element_id": "confirmation_text",
                            "role": "status",
                            "text": "Booking confirmed",
                            "attributes": {"visible": True},
                        })
                    event_log.append({"t": timestamp_iso, "event": "file_created", "path": filename})
                    state_diff["filesystem.added"] = [filename]

            elif atype == "input_text" and element_id == "card_number_input":
                el = find_element("card_number_input")
                if el is not None:
                    text = action.get("text", "")
                    el["text"] = text
                    # Simple Luhn-ish check: use seed parity or length to mark valid
                    state.setdefault("forms", {})["card_valid"] = len(text.replace(" ", "")) in (15, 16)
                    event_log.append({"t": timestamp_iso, "event": "text_input", "element": element_id, "text_len": len(text)})
                else:
                    internal_result = {"result": "rejected", "reason": "target not found"}
                    event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})

            elif atype == "noop":
                event_log.append({"t": timestamp_iso, "event": "noop"})
            else:
                # Unknown or unhandled action → no effect, perceptible flash (represented via event_visuals in observation meta)
                internal_result = {"result": "rejected", "reason": "unhandled action"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})

        elif tmpl == "email_client":
            # Compose flow
            def set_visible(eid: str, vis: bool):
                el = find_element(eid)
                if el:
                    el.setdefault("attributes", {})["visible"] = vis
            def set_text(eid: str, text: str):
                el = find_element(eid)
                if el:
                    el["text"] = text

            if atype == "click" and element_id == "compose_btn":
                set_visible("to_input", True)
                set_visible("subject_input", True)
                set_visible("body_input", True)
                set_visible("status_banner", False)
                event_log.append({"t": timestamp_iso, "event": "compose_open"})

            elif atype == "input_text" and element_id in {"to_input", "subject_input", "body_input"}:
                el = find_element(element_id)
                if el is not None:
                    txt = action.get("text", "")
                    el["text"] = txt
                    # Update compose readiness
                    forms = state.setdefault("forms", {})
                    comp = forms.setdefault("compose", {"to": "", "subject": "", "body": "", "ready": False})
                    if element_id == "to_input":
                        comp["to"] = txt
                    elif element_id == "subject_input":
                        comp["subject"] = txt
                    else:
                        comp["body"] = txt

                    to_ok = ("@" in comp.get("to", "")) and ("." in comp.get("to", ""))
                    subj_ok = len(comp.get("subject", "")) > 0
                    body_ok = len(comp.get("body", "")) > 0
                    ready = bool(to_ok and subj_ok and body_ok)
                    comp["ready"] = ready
                    # toggle send button enable
                    send_btn = find_element("send_btn")
                    if send_btn:
                        send_btn.setdefault("attributes", {})["enabled"] = ready
                    event_log.append({"t": timestamp_iso, "event": "text_input", "element": element_id})
                else:
                    internal_result = {"result": "rejected", "reason": "target not found"}
                    event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})

            elif atype == "click" and element_id == "send_btn":
                ready = state.get("forms", {}).get("compose", {}).get("ready", False)
                send_btn = find_element("send_btn")
                enabled = send_btn and send_btn.get("attributes", {}).get("enabled", False)
                if not (ready and enabled):
                    internal_result = {"result": "rejected", "reason": "compose incomplete"}
                    set_text("status_banner", "Please complete all fields")
                    set_visible("status_banner", True)
                    event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})
                else:
                    # Simulate sending: write outbox file deterministically by seed
                    out_dir = "/home/user/outbox/"
                    state.setdefault("filesystem", {}).setdefault(out_dir, {"kind": "dir"})
                    filename = f"{out_dir}sent-{state['seed']}.eml"
                    state["filesystem"][filename] = {
                        "bytes": 64,
                        "kind": "eml",
                        "created_at": timestamp_iso,
                    }
                    set_text("status_banner", "Message sent")
                    set_visible("status_banner", True)
                    event_log.append({"t": timestamp_iso, "event": "file_created", "path": filename})
                    state_diff["filesystem.added"] = [filename]

            elif atype == "noop":
                event_log.append({"t": timestamp_iso, "event": "noop"})
            else:
                internal_result = {"result": "rejected", "reason": "unhandled action"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})

        elif tmpl == "file_manager":
            def set_text(eid: str, text: str):
                for el in state.get("ui_elements", []):
                    if el.get("element_id") == eid:
                        el["text"] = text
                        el.setdefault("attributes", {})["visible"] = True
                        return
            if atype == "click" and element_id == "new_file_btn":
                # Create untitled file in /home/user/
                path = "/home/user/untitled.txt"
                state.setdefault("filesystem", {})[path] = {"bytes": 0, "kind": "txt", "created_at": timestamp_iso}
                set_text("status_banner", "Created untitled.txt")
                event_log.append({"t": timestamp_iso, "event": "file_created", "path": path})
                state_diff["filesystem.added"] = [path]
            elif atype == "noop":
                event_log.append({"t": timestamp_iso, "event": "noop"})
            else:
                internal_result = {"result": "rejected", "reason": "unhandled action"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})
        else:
            # Other templates: keep simple behavior
            if atype == "noop":
                event_log.append({"t": timestamp_iso, "event": "noop"})
            else:
                internal_result = {"result": "rejected", "reason": "template not implemented"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})

        # Commit new state
        self._episodes[episode_id] = state
        state_digest = _sha256_digest(state)
        observation = self._make_observation(state, last_action=action, internal_result=internal_result)

        out = {
            "observation": observation,
            "internal_result": internal_result,
            "event_log": event_log,
            "state_diff": state_diff,
            "state_digest": state_digest,
            "terminal": terminal,
            "reward_hint": reward_hint,
        }
        validate_observation(out["observation"])
        return out

    def get_state_summary(self, episode_id: str) -> Dict[str, Any]:
        if episode_id not in self._episodes:
            raise KeyError("Unknown episode_id")
        st = self._episodes[episode_id]
        return {
            "template": st.get("template"),
            "page": st.get("page"),
            "filesystem_paths": sorted(list(st.get("filesystem", {}).keys())),
            "ui_element_ids": [e.get("element_id") for e in st.get("ui_elements", [])],
        }

    def snapshot(self, episode_id: str) -> Dict[str, Any]:
        if episode_id not in self._episodes:
            raise KeyError("Unknown episode_id")
        return deepcopy(self._episodes[episode_id])

    # ---------------------------- Internal utils -------------------------- #
    def _seed_ui(self, template: Dict[str, Any], seed: int) -> Any:
        # Deterministically map base template into UI elements
        base_elements = template.get("ui_elements", [])
        # For now, pass through with a deterministic ordering
        return sorted(base_elements, key=lambda e: e.get("element_id", ""))

    def _make_observation(self, state: Dict[str, Any], last_action: Any = None, internal_result: Any = None) -> Dict[str, Any]:
        # Never include internal verdicts; only percepts.
        visible_elements = []
        for el in state.get("ui_elements", []):
            attrs = el.get("attributes", {})
            if attrs.get("visible", True):
                visible_elements.append({
                    "element_id": el.get("element_id"),
                    "role": el.get("role"),
                    "text": el.get("text", ""),
                    "attributes": attrs,
                })

        audio_events = []
        if internal_result and internal_result.get("result") == "rejected":
            audio_events.append({"type": "beep", "volume": 0.6, "timestamp": _now_iso()})

        observation = {
            "timestamp": _now_iso(),
            "screenshot_id": f"s-{state.get('template')}-{state.get('seed')}",
            "ui_elements": visible_elements,
            "audio_events": audio_events,
            "meta": {
                "page": state.get("page"),
                "event_visuals": "flash" if internal_result and internal_result.get("result") == "rejected" else None,
            },
        }
        # Ensure no internal fields leak
        if "internal_result" in observation:
            del observation["internal_result"]
        if "reason" in observation:
            del observation["reason"]
        return observation
