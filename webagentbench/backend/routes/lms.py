"""LMS environment API routes (stub).

Provides session create and evaluate endpoints. Full CRUD routes
(assignments, grades, modules, etc.) will be added in a later task.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...tasks._evaluator import evaluate as unified_evaluate
from ...tasks._registry import get_task
from ..models.lms import LMSState
from ..security import require_controller_access
from ..state import SessionManager

router = APIRouter(prefix="/api/env/lms", tags=["lms"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    task_id: str
    seed: int | None = None
    degradation: dict | None = None
    variant_filename: str | None = None


class SessionScopedRequest(BaseModel):
    session_id: str


class EvaluateRequest(SessionScopedRequest):
    task_id: str | None = None
    benchmark_state: dict[str, Any] = Field(default_factory=dict)
    trajectory: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_session_manager(request: Request) -> SessionManager:
    session_manager = getattr(request.app.state, "session_manager", None)
    if session_manager is None:
        raise HTTPException(status_code=500, detail="SessionManager is not configured on app.state")
    return session_manager


def _lms_state(session_manager: SessionManager, session_id: str) -> LMSState:
    try:
        state = session_manager.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not isinstance(state, LMSState):
        raise HTTPException(status_code=404, detail=f"Session {session_id} is not an LMS session")
    return state


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@router.post("/session")
def create_session(
    body: SessionCreateRequest,
    request: Request = None,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    task = get_task(body.task_id)
    if task.env_id != "lms":
        raise HTTPException(status_code=404, detail=f"Unknown LMS task_id: {body.task_id}")

    session_id, resolved_targets, actual_seed = session_manager.create_session("lms", body.task_id, body.seed)
    state = session_manager.get(session_id)

    return {
        "session_id": session_id,
        "task_id": body.task_id,
        "seed": actual_seed,
        "student": state.student.model_dump() if isinstance(state, LMSState) else {},
        "courses_count": len(state.courses) if isinstance(state, LMSState) else 0,
    }


@router.post("/evaluate")
def evaluate_session(
    body: EvaluateRequest,
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    try:
        require_controller_access(request)
        state = session_manager.get(body.session_id)
        if body.benchmark_state is not None:
            session_manager.set_benchmark_state(body.session_id, body.benchmark_state)
        if body.task_id and body.task_id != state.task_id:
            raise HTTPException(
                status_code=400,
                detail=f"Session {body.session_id} is bound to task {state.task_id!r}, not {body.task_id!r}",
            )
        task = get_task(state.task_id)
        return unified_evaluate(
            task,
            server_state=state,
            targets=state.resolved_targets,
            trajectory=body.trajectory or [],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
