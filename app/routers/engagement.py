from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import verify_token
from app.routers.users import get_db

router = APIRouter(prefix="/engagement", tags=["Engagement"])

PROMPT_COOLDOWN_DAYS = 3
POST_COOLDOWN_DAYS = 2


@router.get("/prompts/next", response_model=Optional[schemas.EngagementPromptResponse])
def get_next_prompt(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    now = datetime.now(timezone.utc)

    latest_event = (
        db.query(models.UserPromptEvent)
        .filter(models.UserPromptEvent.user_clerk_id == clerk_id)
        .order_by(models.UserPromptEvent.created_at.desc())
        .first()
    )

    if latest_event and latest_event.created_at:
        event_created_at = latest_event.created_at
        if event_created_at.tzinfo is None:
            event_created_at = event_created_at.replace(tzinfo=timezone.utc)

        if event_created_at >= now - timedelta(days=PROMPT_COOLDOWN_DAYS):
            return None

    latest_post = (
        db.query(models.Post.created_at, models.Post.id)
        .filter(models.Post.author_clerk_id == clerk_id)
        .order_by(models.Post.created_at.desc())
        .first()
    )

    if latest_post and latest_post.created_at:
        post_created_at = latest_post.created_at
        if post_created_at.tzinfo is None:
            post_created_at = post_created_at.replace(tzinfo=timezone.utc)

        if post_created_at >= now - timedelta(days=POST_COOLDOWN_DAYS):
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
