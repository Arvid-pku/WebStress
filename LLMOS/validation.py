import json
import os
from typing import Any, Dict

_JSONSCHEMA = None
try:
    import jsonschema  # type: ignore

    _JSONSCHEMA = jsonschema
except Exception:  # pragma: no cover
    _JSONSCHEMA = None


def _load_schema(name: str) -> Dict[str, Any]:
    here = os.path.dirname(__file__)
    path = os.path.join(here, "schema", f"{name}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _require_keys(obj: Dict[str, Any], keys: list[str], ctx: str) -> None:
    for k in keys:
        if k not in obj:
            raise ValueError(f"{ctx}: missing required key '{k}'")


def validate_action(action: Dict[str, Any]) -> None:
    schema = _load_schema("action")
    if _JSONSCHEMA is not None:
        _JSONSCHEMA.validate(action, schema)
        return
    _require_keys(action, ["type"], "action")
    if not isinstance(action["type"], str):
        raise ValueError("action.type must be string")
    allowed = schema["properties"]["type"]["enum"]
    if action["type"] not in allowed:
        raise ValueError(f"action.type must be one of {allowed}")
    if "target" in action and not isinstance(action["target"], dict):
        raise ValueError("action.target must be object if present")
    if action["type"] == "input_text" and "text" not in action:
        raise ValueError("input_text action requires 'text'")


def validate_observation(obs: Dict[str, Any]) -> None:
    if _JSONSCHEMA is not None:
        _JSONSCHEMA.validate(obs, _load_schema("observation"))
    else:
        _require_keys(obs, ["timestamp", "screenshot_id", "ui_elements", "audio_events", "meta"], "observation")
    if "internal_result" in obs or "reason" in obs:
        raise ValueError("observation must not contain internal_result or reason")
    if not isinstance(obs["ui_elements"], list):
        raise ValueError("observation.ui_elements must be an array")


def validate_instruction(instr: Dict[str, Any]) -> None:
    if _JSONSCHEMA is not None:
        _JSONSCHEMA.validate(instr, _load_schema("instruction"))
        return
    _require_keys(instr, ["id", "description", "template", "success_criteria", "difficulty", "time_limit"], "instruction")
    if not isinstance(instr["success_criteria"], list):
        raise ValueError("instruction.success_criteria must be array")


def validate_state(state: Dict[str, Any]) -> None:
    if _JSONSCHEMA is not None:
        _JSONSCHEMA.validate(state, _load_schema("state"))
        return
    _require_keys(state, ["seed", "template", "ui_elements", "filesystem", "random_seed"], "state")


def validate_judge_output(out: Dict[str, Any]) -> None:
    if _JSONSCHEMA is not None:
        _JSONSCHEMA.validate(out, _load_schema("judge_output"))
        return
    _require_keys(out, ["score", "feedback", "subscores"], "judge_output")
    s = out["score"]
    if not (isinstance(s, (int, float)) and 0.0 <= float(s) <= 1.0):
        raise ValueError("judge_output.score must be in [0,1]")
