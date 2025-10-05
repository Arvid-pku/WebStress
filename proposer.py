from typing import Any, Dict, List


class Proposer:
    """Simple adaptive task proposer."""

    def propose_next(self, agent_id: str, recent_episodes: List[Dict[str, Any]], global_task_pool: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        avg = None
        if recent_episodes:
            scores = [e.get("score", 0.0) for e in recent_episodes if isinstance(e.get("score", None), (int, float))]
            if scores:
                avg = sum(scores) / len(scores)

        if avg is None:
            difficulty = "easy"
        elif avg > 0.85:
            difficulty = "hard"
        elif avg < 0.5:
            difficulty = "easy"
        else:
            difficulty = "medium"

        # Very small set of deterministic templates
        if difficulty == "easy":
            instr = {
                "id": "instr-file",
                "description": "Confirm payment without valid card to trigger error.",
                "template": "flight_booking",
                "difficulty": difficulty,
                "time_limit": 30,
                "success_criteria": [
                    {"predicate": "element_text_contains:Invalid card number", "weight": 1.0}
                ],
            }
        else:
            instr = {
                "id": "instr-ticket",
                "description": "Book a flight and save the ticket.",
                "template": "flight_booking",
                "difficulty": difficulty,
                "time_limit": 60,
                "success_criteria": [
                    {"predicate": "file_exists:/home/user/tickets.pdf", "weight": 1.0},
                    {"predicate": "element_text_contains:Booking confirmed", "weight": 1.0}
                ],
            }

        return instr

