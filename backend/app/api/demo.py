"""Demo endpoints. They exist ONLY when DEMO_MODE=true; otherwise every path 404s."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.db.seed import reset_demo, seed_if_needed
from app.services.demo_story import run_story
from app.services.paypal_service import PayPalService
from app.api.actions import paypal_dep

router = APIRouter(prefix="/demo", tags=["demo"])


def require_demo_mode() -> None:
    """404 for the whole router when DEMO_MODE is false (MASTER 4.3)."""
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo endpoints are disabled because DEMO_MODE is not true.",
        )


@router.post("/reset", summary="Delete demo rows (never LIVE ones)", dependencies=[Depends(require_demo_mode)])
def reset(db: Session = Depends(get_db)) -> dict[str, object]:
    return reset_demo(db)


@router.post("/seed", summary="Seed the 15 story orders if the DB is empty", dependencies=[Depends(require_demo_mode)])
def seed(db: Session = Depends(get_db)) -> dict[str, object]:
    inserted = seed_if_needed(db)
    return {"inserted": inserted}


@router.post("/run-story", summary="Play the whole V1 story end to end", dependencies=[Depends(require_demo_mode)])
async def story(
    db: Session = Depends(get_db), paypal: PayPalService = Depends(paypal_dep)
) -> dict[str, object]:
    return await run_story(db, paypal)
