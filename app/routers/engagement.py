from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import verify_token
from app.routers.users import get_db

router = APIRouter(prefix="/engagement", tags=["Engagement"])

MAX_PROMPT_SHOWS_PER_DAY = 2
PROMPT_INTERACTION_COOLDOWN_HOURS = 12
PROMPT_COOLDOWN_EVENT_TYPES = {"dismissed", "posted"}


def get_utc_day_window(now: datetime) -> tuple[datetime, datetime]:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start, day_start + timedelta(days=1)


@router.get("/prompts/next", response_model=Optional[schemas.EngagementPromptResponse])
def get_next_prompt(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    now = datetime.now(timezone.utc)
    day_start, next_day_start = get_utc_day_window(now)

    shown_events_today = (
        db.query(func.count(models.UserPromptEvent.id))
        .filter(models.UserPromptEvent.user_clerk_id == clerk_id)
        .filter(models.UserPromptEvent.event_type == "shown")
        .filter(
            and_(
                models.UserPromptEvent.created_at >= day_start,
                models.UserPromptEvent.created_at < next_day_start,
            )
        )
        .scalar()
    )

    if (shown_events_today or 0) >= MAX_PROMPT_SHOWS_PER_DAY:
        return None

    latest_event = (
        db.query(models.UserPromptEvent)
        .filter(models.UserPromptEvent.user_clerk_id == clerk_id)
        .order_by(models.UserPromptEvent.created_at.desc())
        .first()
    )

    if (
        latest_event
        and latest_event.event_type in PROMPT_COOLDOWN_EVENT_TYPES
        and latest_event.created_at
    ):
        event_created_at = latest_event.created_at
        if event_created_at.tzinfo is None:
            event_created_at = event_created_at.replace(tzinfo=timezone.utc)

        cooldown_cutoff = now - timedelta(hours=PROMPT_INTERACTION_COOLDOWN_HOURS)
        if event_created_at >= cooldown_cutoff:
            return None

    prompts = (
        db.query(models.EngagementPrompt)
        .filter(models.EngagementPrompt.is_active == True)
        .order_by(models.EngagementPrompt.created_at.desc())
        .limit(2)
        .all()
    )

    if not prompts:
        return None

    if latest_event and latest_event.prompt_id == prompts[0].id and len(prompts) > 1:
        return prompts[1]

    return prompts[0]


@router.post("/prompts/{prompt_id}/event")
def record_prompt_event(
    prompt_id: int,
    event: schemas.PromptEventCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    prompt = (
        db.query(models.EngagementPrompt)
        .filter(models.EngagementPrompt.id == prompt_id)
        .first()
    )

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    new_event = models.UserPromptEvent(
        prompt_id=prompt_id,
        user_clerk_id=clerk_id,
        event_type=event.event_type,
    )

    db.add(new_event)
    db.commit()

    return {"success": True}
