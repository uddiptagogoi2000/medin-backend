import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def load_engagement_module(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/testdb")

    class DummyResponse:
        def json(self):
            return {"keys": []}

    monkeypatch.setattr("requests.get", lambda url: DummyResponse())

    for module_name in [
        "app.auth",
        "app.routers.engagement",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]

    return importlib.import_module("app.routers.engagement")


class FakeQuery:
    def __init__(self, *, scalar_result=None, first_result=None, all_result=None):
        self.scalar_result = scalar_result
        self.first_result = first_result
        self.all_result = all_result

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def scalar(self):
        return self.scalar_result

    def first(self):
        return self.first_result

    def all(self):
        return self.all_result


class FakeDB:
    def __init__(self, queries):
        self.queries = list(queries)

    def query(self, *args, **kwargs):
        return self.queries.pop(0)


def set_now(monkeypatch, engagement_module, now):
    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return now.replace(tzinfo=None)
            return now.astimezone(tz)

    monkeypatch.setattr(engagement_module, "datetime", FixedDateTime)


def make_prompt(prompt_id, created_at):
    return SimpleNamespace(
        id=prompt_id,
        title=f"Prompt {prompt_id}",
        body=f"Body {prompt_id}",
        suggested_tags=[],
        is_active=True,
        created_at=created_at,
    )


def make_event(prompt_id, created_at, event_type="shown"):
    return SimpleNamespace(
        id=1,
        prompt_id=prompt_id,
        user_clerk_id="user-1",
        event_type=event_type,
        created_at=created_at,
    )


def test_returns_prompt_when_no_shown_events_today(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(2, now)
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=None),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 2


def test_returns_prompt_when_one_shown_event_today(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(3, now)
    latest_event = make_event(1, now - timedelta(hours=1))
    db = FakeDB(
        [
            FakeQuery(scalar_result=1),
            FakeQuery(first_result=latest_event),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 3


def test_returns_none_when_two_shown_events_today(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    db = FakeDB([FakeQuery(scalar_result=2)])

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result is None


def test_ignores_non_shown_events_in_daily_limit(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(4, now)
    latest_event = make_event(1, now - timedelta(minutes=30), event_type="clicked_post")
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=latest_event),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 4


def test_ignores_shown_events_from_previous_day(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(5, now)
    previous_day_event = make_event(1, now - timedelta(days=1, minutes=1))
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=previous_day_event),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 5


def test_returns_none_during_dismissed_cooldown(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_event = make_event(1, now - timedelta(hours=2), event_type="dismissed")
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=latest_event),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result is None


def test_returns_none_during_posted_cooldown(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_event = make_event(1, now - timedelta(hours=3), event_type="posted")
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=latest_event),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result is None


def test_allows_prompt_after_dismissed_cooldown_expires(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 13, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(7, now)
    latest_event = make_event(1, now - timedelta(hours=13), event_type="dismissed")
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=latest_event),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 7


def test_recent_posts_do_not_suppress_prompts(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_prompt = make_prompt(6, now)
    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=None),
            FakeQuery(all_result=[latest_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 6


def test_avoids_repeating_latest_prompt_when_second_option_exists(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    latest_event = make_event(10, now - timedelta(hours=2))
    newest_prompt = make_prompt(10, now)
    second_prompt = make_prompt(9, now - timedelta(minutes=1))
    db = FakeDB(
        [
            FakeQuery(scalar_result=1),
            FakeQuery(first_result=latest_event),
            FakeQuery(all_result=[newest_prompt, second_prompt]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result.id == 9


def test_returns_none_when_no_active_prompts(monkeypatch):
    engagement_module = load_engagement_module(monkeypatch)
    now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
    set_now(monkeypatch, engagement_module, now)

    db = FakeDB(
        [
            FakeQuery(scalar_result=0),
            FakeQuery(first_result=None),
            FakeQuery(all_result=[]),
        ]
    )

    result = engagement_module.get_next_prompt(payload={"sub": "user-1"}, db=db)

    assert result is None
