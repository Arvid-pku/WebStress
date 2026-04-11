"""Minimal route stub for the Patient Portal environment.

Full endpoint implementation comes in Task 5.  This file provides only the
router definition and the session create/evaluate endpoints required for
the framework wiring to import successfully.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...tasks._evaluator import evaluate as unified_evaluate
from ...tasks._registry import get_task
from ..models.patient_portal import PatientPortalState
from ..security import require_controller_access
from ..state import SessionManager

router = APIRouter(prefix="/api/env/patient_portal", tags=["patient_portal"])


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
# Session lifecycle endpoints
# ---------------------------------------------------------------------------

@router.post("/session/create")
async def create_session(req: SessionCreateRequest, request: Request):
    """Create a seeded Patient Portal session for a task."""
    mgr: SessionManager = request.app.state.session_mgr
    try:
        session_id, targets, seed = mgr.create_session(
            "patient_portal", req.task_id, req.seed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"session_id": session_id, "seed": seed}


@router.post("/session/evaluate")
async def evaluate_session(req: EvaluateRequest, request: Request):
    """Evaluate the current session state against task checks."""
    mgr: SessionManager = request.app.state.session_mgr
    task_id = req.task_id
    if task_id is None:
        state = mgr.get(req.session_id)
        task_id = state.task_id
    task = get_task(task_id)
    state = mgr.get(req.session_id)

    if req.benchmark_state:
        mgr.set_benchmark_state(req.session_id, req.benchmark_state)

    result = unified_evaluate(task, state, trajectory=req.trajectory)
    return result
