"""
Simulator Difficulty Configuration for LLMOS.
Defines curriculum-based difficulty modes for training agents.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DifficultyConfig:
    """Configuration for simulator difficulty."""
    information_density: str = "simple"  # simple, moderate, rich
    signal_noise_ratio: str = "clean"    # clean, moderate, noisy
    determinism: str = "idealized"       # idealized, moderate, hostile
    preset: str = "easy"                 # easy, medium, hard, expert, custom


# Preset configurations
DIFFICULTY_PRESETS = {
    "easy": DifficultyConfig(
        information_density="simple",
        signal_noise_ratio="clean",
        determinism="idealized",
        preset="easy",
    ),
    "medium": DifficultyConfig(
        information_density="moderate",
        signal_noise_ratio="clean",
        determinism="moderate",
        preset="medium",
    ),
    "hard": DifficultyConfig(
        information_density="rich",
        signal_noise_ratio="moderate",
        determinism="moderate",
        preset="hard",
    ),
    "expert": DifficultyConfig(
        information_density="rich",
        signal_noise_ratio="noisy",
        determinism="hostile",
        preset="expert",
    ),
}


# Prompt modifiers for each dimension
INFORMATION_DENSITY_PROMPTS = {
    "simple": """
**Information Density: SIMPLE** -- Show only task-relevant info. Hide dotfiles unless requested. Summarize verbose outputs. Omit metadata. Clean, focused UI.
""",
    "moderate": """
**Information Density: MODERATE** -- Show relevant info plus context. Include common dotfiles if relevant. Moderate detail (first lines, key metadata like sizes/dates). Standard UI detail.
""",
    "rich": """
**Information Density: RICH** -- Full raw output, no summarization. ALL files including dotfiles. Verbose metadata (permissions, timestamps, inodes, ownership). System processes, invisible elements, z-indices, env vars, shell state.
""",
}


SIGNAL_NOISE_PROMPTS = {
    "clean": """
**Signal-to-Noise: CLEAN** -- Perfect formatting (valid JSON, aligned tables). Clear stdout/stderr separation. No encoding errors. Consistent spacing. Clean UI structure.
""",
    "moderate": """
**Signal-to-Noise: MODERATE** -- Mostly clean with occasional quirks. stdout/stderr may interleave. Trailing whitespace, inconsistent indent. Occasional warnings mixed in. Minor UI inconsistencies.
""",
    "noisy": """
**Signal-to-Noise: NOISY** -- Raw ANSI escape codes, interleaved stdout/stderr, broken formatting, progress bars/spinners, garbled text from encoding issues, overlapping UI elements, debug output, deprecation warnings, verbose logging.
""",
}


DETERMINISM_PROMPTS = {
    "idealized": """
**System Determinism: IDEALIZED** -- Commands always succeed if correct. Instant execution. Resources always available. Network always connected. No race conditions.
""",
    "moderate": """
**System Determinism: MODERATE** -- Most commands succeed with occasional warnings. Possible "file not found" edge cases, minor latency, realistic permissions, transient "file in use" errors. No teleporting through workflows; require prerequisite steps and explicit submissions.
""",
    "hostile": """
**System Determinism: HOSTILE** -- Real-world flakiness: resource unavailable, network timeouts, permission denied, disk quota exceeded, partial writes, version mismatches, OOM kills, stale NFS handles. Intermittent failures, race conditions, multi-tick operations, background interference. Strongly avoid shortcutting; require confirmations, retries, missing-info prompts.
""",
}


def get_difficulty_config(
    preset: Optional[str] = None,
    information_density: Optional[str] = None,
    signal_noise_ratio: Optional[str] = None,
    determinism: Optional[str] = None,
) -> DifficultyConfig:
    """
    Get a difficulty configuration.

    Args:
        preset: Use a preset ("easy", "medium", "hard", "expert").
        information_density: Override information density setting.
        signal_noise_ratio: Override signal-to-noise setting.
        determinism: Override determinism setting.

    Returns:
        DifficultyConfig with the specified settings.
    """
    if preset and preset != "custom":
        config = DIFFICULTY_PRESETS.get(preset, DIFFICULTY_PRESETS["easy"])
        # Create a new instance to allow overrides
        config = DifficultyConfig(
            information_density=config.information_density,
            signal_noise_ratio=config.signal_noise_ratio,
            determinism=config.determinism,
            preset=preset,
        )
    else:
        config = DifficultyConfig(preset="custom")

    # Apply overrides
    if information_density:
        config.information_density = information_density
    if signal_noise_ratio:
        config.signal_noise_ratio = signal_noise_ratio
    if determinism:
        config.determinism = determinism

    return config


def build_difficulty_prompt(config: DifficultyConfig) -> str:
    """
    Build the difficulty-specific prompt section.

    Args:
        config: The difficulty configuration.

    Returns:
        Prompt string with difficulty instructions.
    """
    parts = [
        "\n# IMPORTANT (Applies to all difficulty modes)\n"
        "- Your outer response must always be valid JSON (no markdown/code fences).\n"
        "- Any simulated noise (ANSI codes, garbling, interleaving) applies only inside simulated content fields (e.g., terminal output, file contents, UI text), not the wrapper JSON.\n",
        f"\n# DIFFICULTY MODE: {config.preset.upper()}\n",
        INFORMATION_DENSITY_PROMPTS.get(config.information_density, ""),
        SIGNAL_NOISE_PROMPTS.get(config.signal_noise_ratio, ""),
        DETERMINISM_PROMPTS.get(config.determinism, ""),
    ]

    return "\n".join(parts)


def get_difficulty_from_dict(d: dict) -> DifficultyConfig:
    """
    Create a DifficultyConfig from a dictionary.

    Args:
        d: Dictionary with difficulty settings.

    Returns:
        DifficultyConfig instance.
    """
    return get_difficulty_config(
        preset=d.get("preset"),
        information_density=d.get("information_density"),
        signal_noise_ratio=d.get("signal_noise_ratio"),
        determinism=d.get("determinism"),
    )
