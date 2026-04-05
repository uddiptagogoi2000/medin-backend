from typing import Optional

from app import models


def build_full_name(first_name: Optional[str], last_name: Optional[str]) -> Optional[str]:
    full_name = f"{first_name or ''} {last_name or ''}".strip()
    return full_name or None


def populate_user_identity(
    user: models.User,
    first_name: Optional[str],
    last_name: Optional[str],
    avatar_url: Optional[str],
):
    user.first_name = first_name
    user.last_name = last_name
    user.full_name = build_full_name(first_name, last_name)
    user.avatar_url = avatar_url


def get_user_display_name(user: Optional[models.User]) -> str:
    if not user:
        return "Doctor"

    return user.full_name or build_full_name(user.first_name, user.last_name) or "Doctor"
