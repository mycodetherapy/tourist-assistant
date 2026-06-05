"""Маршруты статуса фоновых прогонов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_run_manager
from api.schemas.responses import RunStatusResponse
from services.run_manager import RunManager

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunStatusResponse)
def get_run_status(
    run_id: str,
    run_manager: RunManager = Depends(get_run_manager),
) -> RunStatusResponse:
    record = run_manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Прогон не найден")
    return RunStatusResponse(
        run_id=record.run_id,
        trip_id=record.trip_id,
        status=record.status,
        error=record.error,
        version_id=record.version_id,
    )
