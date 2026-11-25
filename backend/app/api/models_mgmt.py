"""Model management API endpoints for local AI writing detection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_detection.model_registry import activate_model, list_models, verify_model
from app.db import get_db
from app.security import require_auth

router = APIRouter(prefix="/models", tags=["models"], dependencies=[Depends(require_auth)])


@router.get("")
def get_models(db: Session = Depends(get_db)) -> dict:
    return list_models(db)


@router.post("/{model_id}/verify")
def verify_model_endpoint(model_id: str) -> dict:
    try:
        return verify_model(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{model_id}/activate")
def activate_model_endpoint(model_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return activate_model(model_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
