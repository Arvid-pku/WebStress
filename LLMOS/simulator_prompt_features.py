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
        "low": "Render a compact scene: ~3–5 ui_elements, essential attributes only, tiny event_log/network_log snippets.",
        "medium": "Render a balanced scene: ~5–8 ui_elements with useful attributes, light context cues, short status or progress notes.",
        "high": "Render an information-dense scene: include extensive ui_elements with attributes (visible/enabled/role/state), nested panels, tooltips, status areas, and descriptive event_log/network_log entries that capture the breadth of the page.",
    }
    return mapping[level]


def build_feature_block(features: SimulatorPromptFeatures) -> str:
    lines: list[str] = []

    def _append_section(title: str, bullet_points: list[str], mandatory: bool = False) -> None:
        if not bullet_points:
            return
        label = f"- **{title}**"
        if mandatory:
            label += " (MANDATORY)"
        lines.append(label)
        for point in bullet_points:
            lines.append(f"  - {point}")

    if features.observation_granularity != DEFAULT_GRANULARITY:
        _append_section(
            f"Observation fidelity override — {features.observation_granularity.upper()}",
            [
                _granularity_text(features.observation_granularity),
                "Match ui_elements, meta, event_log, and network_log density to this level for every response.",
            ],
            mandatory=True,
        )

    failure_points: list[str] = [
        "During rejection you must emit exactly one beep audio_event, set state_ops=[], and leave the rest of the observation untouched except for the explicit rejection cue.",
        "Always keep `internal_result.reason` as a compact label (e.g., `invalid_action`, `unsupported_target`).",
    ]
    if features.failure_feedback.describe_result:
        failure_points.append(
            "Describe the immediate visible effect of the failed action inside the observation text (e.g., highlight that nothing moved, a dialog stayed closed, etc.)."
        )
    if features.failure_feedback.explain_cause:
        failure_points.append(
            "Explain the most plausible underlying cause for the failure (missing permission, disabled control, validation error) using concise language."
        )
    if features.failure_feedback.provide_hints:
        failure_points.append(
            "Offer a short, actionable hint for recovery (what to click next, which prerequisite is missing)."
        )
    if (
        not features.failure_feedback.describe_result
        and not features.failure_feedback.explain_cause
        and not features.failure_feedback.provide_hints
    ):
        failure_points.append(
            "When no feedback directives are enabled, do not add extra commentary—only the observation itself should change to reflect the failed state."
        )
    _append_section("Failure handling discipline", failure_points, mandatory=True)

    state_diversity_points: list[str] = []
    if features.data_diversity:
        state_diversity_points.append(
            "Data diversity: populate lists, tables, feeds, or directories with substantial, varied domain data so every populated view feels realistic and information-dense (large contact lists, many flights, long email threads, etc.). Keep the diversified corpus consistent for identical seeds."
        )
    if features.functional_diversity:
        state_diversity_points.append(
            "Functional diversity: expose multiple actionable controls and deep navigation paths so the agent must reason about which among many plausible operations best advances the task."
        )
    _append_section("State diversity controls", state_diversity_points)

    dynamics_points: list[str] = []
    if features.stochastic_transitions:
        dynamics_points.append(
            "Let transitions behave like a realistic UI: when an action should open a dialog, navigate, or update state, perform that natural transition without forcing artificial determinism or randomness."
        )
    if features.unreliable_transitions:
        dynamics_points.append(
            "Occasionally simulate instability: certain actions may intermittently do nothing, require a retry, or trigger an unexpected but plausible alternate effect. Reflect the outcome in state_ops/observation so the agent must adapt."
        )
    if features.adversarial_logic:
        dynamics_points.append(
            "Adversarial logic: deliberately introduce obstacles or distractions (extra authentication prompts, blocking overlays, policy gates, conflicting instructions, tight timing, etc.) so successful completion demands more deliberate planning and failure becomes more likely if the agent rushes."
        )
    if features.noise_injection:
        dynamics_points.append(
            "Noise injection: weave in irrelevant but believable observation content (background system messages, unrelated notifications, verbose log snippets) that forces the agent to filter signal from noise without altering the true state."
        )
    _append_section("Dynamics and robustness toggles", dynamics_points)

    if (
        features.observation_granularity == DEFAULT_GRANULARITY
        and not state_diversity_points
        and not dynamics_points
    ):
        lines.append("- **Canonical mode**")
        lines.append("  - No optional diversity or robustness features are enabled; operate with deterministic, schema-first behavior.")

    block = "\n".join(lines)
    return block


def build_simulator_prompt(base_prompt: str, features: Optional[SimulatorPromptFeatures] = None) -> str:
    features = features or SimulatorPromptFeatures()
    block = build_feature_block(features)
    if FEATURE_SWITCHBOARD_MARKER in base_prompt:
        return base_prompt.replace(FEATURE_SWITCHBOARD_MARKER, block)
    return f"{base_prompt.rstrip()}\n\n{block}\n"
