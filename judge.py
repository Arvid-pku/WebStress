import re
from typing import Any, Dict, List


class Judge:
    """Deterministic judge with predicate evaluation and weighted scoring."""

    def __init__(self, reject_penalty: float = 0.0) -> None:
        self.reject_penalty = float(reject_penalty)

    def evaluate(
        self,
        instruction: Dict[str, Any],
        start_state_summary: Dict[str, Any],
        end_state_summary: Dict[str, Any],
        episode_log: Dict[str, Any],
    ) -> Dict[str, Any]:
        criteria = instruction.get("success_criteria", [])
        subscores = []

        # Gather final observation if present in log
        last_obs = None
        if episode_log.get("steps"):
            for step in episode_log["steps"]:
                if "observation" in step:
                    last_obs = step["observation"]
        fs_paths = set(end_state_summary.get("filesystem_paths", []))

        for item in criteria:
            predicate = item.get("predicate", "")
            weight = float(item.get("weight", 1.0))
            score = 0.0

            if predicate.startswith("file_exists:"):
                path = predicate.split(":", 1)[1]
                score = 1.0 if path in fs_paths else 0.0

            elif predicate.startswith("element_text_contains:") and last_obs is not None:
                pat = predicate.split(":", 1)[1]
                txt = " ".join(e.get("text", "") for e in last_obs.get("ui_elements", []))
                try:
                    score = 1.0 if re.search(pat, txt) else 0.0
                except re.error:
                    score = 1.0 if pat in txt else 0.0

            subscores.append({"predicate": predicate, "score": float(score), "weight": weight})

        # Weighted aggregate
        if subscores:
            total_w = sum(s.get("weight", 1.0) for s in subscores)
            agg = sum(s.get("weight", 1.0) * s.get("score", 0.0) for s in subscores) / (total_w or 1.0)
        else:
            agg = 0.0

        # Penalty for rejected steps if configured
        if self.reject_penalty > 0.0 and episode_log.get("steps"):
            rejects = 0
            for step in episode_log["steps"]:
                ir = step.get("internal_result", {})
                if ir.get("result") == "rejected":
                    rejects += 1
            if rejects:
                agg = max(0.0, agg - self.reject_penalty * rejects)

        feedback = self._make_feedback(subscores, fs_paths)
        out = {"score": float(max(0.0, min(1.0, agg))), "feedback": feedback, "subscores": subscores}
        return out

    def _make_feedback(self, subscores: List[Dict[str, Any]], fs_paths: set) -> str:
        # Keep concise and actionable
        missed = [s for s in subscores if s.get("score", 0.0) < 1.0]
        if not missed:
            return "All criteria satisfied."
        msgs = []
        for s in missed[:2]:
            pred = s.get("predicate", "")
            if pred.startswith("file_exists:"):
                msgs.append(f"Missing file {pred.split(':',1)[1]}")
            elif pred.startswith("element_text_contains:"):
                msgs.append("Expected text not found")
        return ", ".join(msgs) or "Criteria unmet"

