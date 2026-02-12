"""
Simulator Strictness Configuration for LLMOS.

Controls how strictly the simulator enforces realistic behavior.
Orthogonal to difficulty (noise/chaos) - strictness controls realism/shortcuts.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StrictnessLevel(str, Enum):
    """Strictness presets."""
    LENIENT = "lenient"    # Helpful, forgiving (for demos)
    MODERATE = "moderate"  # Some realism
    STRICT = "strict"      # Realistic, no shortcuts


@dataclass
class StrictnessConfig:
    """Configuration for simulator strictness."""
    level: StrictnessLevel = StrictnessLevel.STRICT

    # Individual settings (can override preset)
    require_double_click_to_open: bool = True      # Apps/files need dblclick
    require_explicit_navigation: bool = True       # No teleporting between pages
    require_form_validation: bool = True           # Forms must be filled correctly
    require_loading_states: bool = True            # Show loading between transitions
    no_task_aware_shortcuts: bool = True           # No convenient shortcuts based on task
    no_answer_hints: bool = True                   # Don't surface correct answers
    enforce_focus_requirements: bool = True        # Must focus input before typing
    realistic_error_messages: bool = True          # Show realistic errors, not helpful hints


# Preset configurations
STRICTNESS_PRESETS = {
    "lenient": StrictnessConfig(
        level=StrictnessLevel.LENIENT,
        require_double_click_to_open=False,
        require_explicit_navigation=False,
        require_form_validation=False,
        require_loading_states=False,
        no_task_aware_shortcuts=False,
        no_answer_hints=False,
        enforce_focus_requirements=False,
        realistic_error_messages=False,
    ),
    "moderate": StrictnessConfig(
        level=StrictnessLevel.MODERATE,
        require_double_click_to_open=True,
        require_explicit_navigation=True,
        require_form_validation=True,
        require_loading_states=False,
        no_task_aware_shortcuts=False,
        no_answer_hints=True,
        enforce_focus_requirements=False,
        realistic_error_messages=True,
    ),
    "strict": StrictnessConfig(
        level=StrictnessLevel.STRICT,
        require_double_click_to_open=True,
        require_explicit_navigation=True,
        require_form_validation=True,
        require_loading_states=True,
        no_task_aware_shortcuts=True,
        no_answer_hints=True,
        enforce_focus_requirements=True,
        realistic_error_messages=True,
    ),
}


def get_strictness_config(preset: str = "strict") -> StrictnessConfig:
    """Get strictness configuration by preset name."""
    return STRICTNESS_PRESETS.get(preset, STRICTNESS_PRESETS["strict"])


def build_strictness_prompt(config: StrictnessConfig) -> str:
    """
    Build the strictness-specific prompt section.

    Args:
        config: The strictness configuration.

    Returns:
        Prompt string with strictness instructions.
    """
    parts = [f"\n# STRICTNESS MODE: {config.level.value.upper()}\n"]

    if config.level == StrictnessLevel.LENIENT:
        parts.append("""
Accept approximate actions (single click can open apps). Help agent when intent is clear. Skip intermediate steps if goal is obvious.
""")
        return "\n".join(parts)

    # Build strict rules
    rules = []

    if config.require_double_click_to_open:
        rules.append("""
**Double-Click Required**: Desktop icons/files/folders need dblclick to open. Single click only selects (highlights, shows info). Exception: taskbar uses single click.""")

    if config.require_explicit_navigation:
        rules.append("""
**No Teleportation**: Every page transition needs explicit navigation. No skipping steps. Must go: click link → loading → new page. No convenient shortcuts based on agent's goal.""")

    if config.require_form_validation:
        rules.append("""
**Form Validation Required**: Empty required fields → validation error, block submit. Invalid format → specific error. Password requirements enforced.""")

    if config.require_loading_states:
        rules.append("""
**Loading States Required**: Operations show loading first, complete on NEXT action. App launch → "Loading..." → (next action) → UI. Same for navigation and search.""")

    if config.no_task_aware_shortcuts:
        rules.append("""
**No Task-Aware Shortcuts (CRITICAL)**: For `hidden_state.task_paths`: create 5+ realistic files with varied names/sizes/timestamps. NO hints ("best_", "correct_"). Randomize order. No pre-populated forms or pre-selected options.""")

    if config.no_answer_hints:
        rules.append("""
**No Answer Hints**: Neutral labels only ("Search Results", not "Best Match"). Don't pre-select or sort to highlight answers. Thought field: describe actions, don't reveal answers.""")

    if config.enforce_focus_requirements:
        rules.append("""
**Focus Requirements**: Text input needs focus first. Keyboard shortcuts need appropriate element focused. Tab order respected. Click input to focus before fill.""")

    if config.realistic_error_messages:
        rules.append("""
**Realistic Error Messages**: "Invalid input" not "Try entering a valid email like user@example.com". Errors must not guide agent to solution.""")

    parts.extend(rules)

    # Add key examples for strict mode
    if config.level == StrictnessLevel.STRICT:
        parts.append("""
**KEY EXAMPLES**: click desktop icon → select only; dblclick → open; click taskbar icon → open. Task thought: describe actions ("Displaying files sorted by date"), never reveal answers.""")

    # Add summary
    parts.append("""
**GOLDEN RULE**: Behave like a REAL computer, not a helpful assistant. No shortcuts, no hints.
""")

    return "\n".join(parts)
