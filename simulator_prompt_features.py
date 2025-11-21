from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

FEATURE_SWITCHBOARD_MARKER = "<<FEATURE_SWITCHBOARD>>"
DEFAULT_GRANULARITY: Literal["low", "medium", "high"] = "medium"


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _validate_level(value: Any, default: Literal["low", "medium", "high"]) -> Literal["low", "medium", "high"]:
    if isinstance(value, str):
        lv = value.strip().lower()
        if lv in {"low", "medium", "high"}:
            return lv  # type: ignore[return-value]
    return default


@dataclass
class FailureFeedbackOptions:
    describe_result: bool = True
    explain_cause: bool = False
    provide_hints: bool = False

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "FailureFeedbackOptions":
        data = data or {}
        return cls(
            describe_result=_as_bool(data.get("describe_result"), True),
            explain_cause=_as_bool(data.get("explain_cause"), False),
            provide_hints=_as_bool(data.get("provide_hints"), False),
        )

    def to_dict(self) -> Dict[str, bool]:
        return {
            "describe_result": bool(self.describe_result),
            "explain_cause": bool(self.explain_cause),
            "provide_hints": bool(self.provide_hints),
        }

    def describe(self) -> str:
        enabled = []
        if self.describe_result:
            enabled.append("describe the immediate effect")
        if self.explain_cause:
            enabled.append("explain the cause")
        if self.provide_hints:
            enabled.append("offer concise format hints")
        if not enabled:
            return "minimal rejection note only"
        return ", ".join(enabled)


@dataclass
class SimulatorPromptFeatures:
    observation_granularity: Literal["low", "medium", "high"] = DEFAULT_GRANULARITY
    failure_feedback: FailureFeedbackOptions = field(default_factory=FailureFeedbackOptions)
    data_diversity: bool = False
    functional_diversity: bool = False
    stochastic_transitions: bool = False
    unreliable_transitions: bool = False
    adversarial_logic: bool = False
    noise_injection: bool = False

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SimulatorPromptFeatures":
        data = data or {}
        return cls(
            observation_granularity=_validate_level(data.get("observation_granularity"), DEFAULT_GRANULARITY),
            failure_feedback=FailureFeedbackOptions.from_dict(data.get("failure_feedback")),
            data_diversity=_as_bool(data.get("data_diversity"), False),
            functional_diversity=_as_bool(data.get("functional_diversity"), False),
            stochastic_transitions=_as_bool(data.get("stochastic_transitions"), False),
            unreliable_transitions=_as_bool(data.get("unreliable_transitions"), False),
            adversarial_logic=_as_bool(data.get("adversarial_logic"), False),
            noise_injection=_as_bool(data.get("noise_injection"), False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_granularity": self.observation_granularity,
            "failure_feedback": self.failure_feedback.to_dict(),
            "data_diversity": bool(self.data_diversity),
            "functional_diversity": bool(self.functional_diversity),
            "stochastic_transitions": bool(self.stochastic_transitions),
            "unreliable_transitions": bool(self.unreliable_transitions),
            "adversarial_logic": bool(self.adversarial_logic),
            "noise_injection": bool(self.noise_injection),
        }

def _granularity_text(level: Literal["low", "medium", "high"]) -> str:
    mapping = {
        "low": "LOW — terse observation text, 3-5 elements max, minimal event_log.",
        "medium": "MEDIUM — balanced detail (5-8 elements), light context cues.",
        "high": "HIGH — richly described but still compact, include helpful affordances.",
    }
    return mapping[level]


def build_feature_block(features: SimulatorPromptFeatures) -> str:
    lines = [
        "Feature switchboard (configured by orchestrator). Read every line before emitting a response:",
    ]

    has_optional = False

    def _append_section(title: str, bullet_points: list[str]) -> None:
        if not bullet_points:
            return
        lines.append(f"- {title}:")
        for point in bullet_points:
            lines.append(f"  * {point}")

    if features.observation_granularity != DEFAULT_GRANULARITY:
        has_optional = True
        _append_section(
            "Observation fidelity override",
            [
                _granularity_text(features.observation_granularity),
                "Match ui_elements, meta, event_log, and network_logs density to this level—no more, no less.",
            ],
        )

    failure_points = [
        f"When rejecting actions: {features.failure_feedback.describe()} and keep reasons as compact labels (e.g., 'invalid_action').",
        "On rejection emit exactly one beep audio_event, return state_ops=[], and leave the rest of the observation untouched except for the error cue.",
    ]
    _append_section("Failure handling discipline", failure_points)

    state_diversity_points: list[str] = []
    if features.data_diversity:
        has_optional = True
        state_diversity_points.append(
            "Data diversity: rotate numbers, proper names, and lightweight file contents per step seed; never break schema invariants."
        )
    if features.functional_diversity:
        has_optional = True
        state_diversity_points.append(
            "Functional diversity: reshuffle layouts/components or swap plausible widgets while preserving affordances and identifiers when possible."
        )
    _append_section("State diversity controls", state_diversity_points)

    dynamics_points: list[str] = []
    if features.stochastic_transitions:
        has_optional = True
        dynamics_points.append(
            "Stochastic transitions: when multiple valid results exist, pick one using a deterministic rule tied to the provided seed (e.g., even seeds favor the first option, odd seeds the second) and fully commit observation/state_ops to that branch so identical seeds stay consistent while different seeds may diverge."
        )
    if features.unreliable_transitions:
        has_optional = True
        dynamics_points.append(
            'Unreliable transitions: at low frequency emit a "transient_failure" rejection even for valid inputs; never mutate state when doing so.'
        )
    if features.adversarial_logic:
        has_optional = True
        dynamics_points.append(
            "Adversarial logic: spotlight subtle inconsistencies, edge-case warnings, or hidden blockers without fabricating impossible conditions."
        )
    if features.noise_injection:
        has_optional = True
        dynamics_points.append(
            "Noise injection: add harmless notifications, background chatter, or superfluous log lines that do not alter task semantics or violate schemas."
        )
    _append_section("Dynamics and robustness toggles", dynamics_points)

    if not has_optional:
        lines.append("- No optional diversity/robustness features are enabled; operate with canonical deterministic behavior.")

    block = "\n".join(lines)
    return block


def build_simulator_prompt(base_prompt: str, features: Optional[SimulatorPromptFeatures] = None) -> str:
    features = features or SimulatorPromptFeatures()
    block = build_feature_block(features)
    if FEATURE_SWITCHBOARD_MARKER in base_prompt:
        return base_prompt.replace(FEATURE_SWITCHBOARD_MARKER, block)
    return f"{base_prompt.rstrip()}\n\n{block}\n"
