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
        # Initialize a generic desktop regardless of instruction template.
        template_name = "desktop"
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

        # Generic desktop behavior; deeper transitions handled by LLM wrapper when enabled.
        tmpl = state.get("template")
        if tmpl == "desktop":
            if atype == "double_click" and element_id in {"icon_settings", "icon_browser", "icon_files"}:
                # Valid open action; core does not change state here — LLMSimulator may mutate state.
                event_log.append({"t": timestamp_iso, "event": "open_app", "app": element_id})
                internal_result = {"result": "ok", "reason": "opened app"}
            elif atype in {"click", "right_click", "double_click"}:
                # Clicks on non-openable or missing elements are perceptual only (selection/flash)
                if element_id and find_element(element_id):
                    event_log.append({"t": timestamp_iso, "event": "select", "element": element_id})
                    internal_result = {"result": "ok", "reason": "selected"}
                else:
                    internal_result = {"result": "rejected", "reason": "target not found"}
                    event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})
            elif atype == "noop" or atype == "scroll" or atype == "hotkey":
                # No effect on canonical state
                event_log.append({"t": timestamp_iso, "event": atype})
                internal_result = {"result": "ok", "reason": atype}
            elif atype == "input_text":
                # No text boxes on desktop by default
                internal_result = {"result": "rejected", "reason": "no text target"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})
            else:
                internal_result = {"result": "rejected", "reason": "unhandled action"}
                event_log.append({"t": timestamp_iso, "event": "rejected", "action": action, "reason": internal_result["reason"]})
        else:
            # Unknown template; treat as no-op environment
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
