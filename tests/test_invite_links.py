import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException


def load_users_module(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/testdb")

    class DummyResponse:
        def json(self):
            return {"keys": []}

    monkeypatch.setattr("requests.get", lambda url: DummyResponse())

    for module_name in [
        "app.auth",
        "app.routers.users",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]

    return importlib.import_module("app.routers.users")


class FakeQuery:
    def __init__(self, *, first_result=None):
        self.first_result = first_result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result


class FakeDB:
    def __init__(self, queries=None):
        self.queries = list(queries or [])
        self.added = []
        self.commits = 0

    def query(self, *args, **kwargs):
        return self.queries.pop(0)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def make_clerk_user(email):
    email_address = SimpleNamespace(id="email_1", email_address=email)
    return SimpleNamespace(
        first_name="Test",
        last_name="Doctor",
        has_image=False,
        image_url=None,
        primary_email_address_id="email_1",
        email_addresses=[email_address],
    )


def test_create_invite_link_returns_full_url(monkeypatch):
    users_module = load_users_module(monkeypatch)
    monkeypatch.setenv("ADMIN_INVITE_SECRET", "topsecret")
    monkeypatch.setenv("INVITE_SIGNUP_URL", "https://medin.app/sign-up")

    db = FakeDB()
    response = users_module.create_invite_link(
        data=users_module.schemas.InviteLinkCreateRequest(note="cardiology outreach"),
        db=db,
        x_admin_secret="topsecret",
    )

    created_invite = db.added[0]

    assert response.invite_url.startswith("https://medin.app/sign-up?invite=")
    assert response.expires_at > datetime.now(timezone.utc) + timedelta(days=13)
    assert created_invite.invite_type == "link"
    assert created_invite.token_hash
    assert created_invite.note == "cardiology outreach"
    assert db.commits == 1


def test_create_invite_link_rejects_invalid_secret(monkeypatch):
    users_module = load_users_module(monkeypatch)
    monkeypatch.setenv("ADMIN_INVITE_SECRET", "topsecret")

    db = FakeDB()

    try:
        users_module.create_invite_link(
            data=users_module.schemas.InviteLinkCreateRequest(),
            db=db,
            x_admin_secret="wrong",
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Invalid admin secret"
    else:
        raise AssertionError("Expected invite creation to be rejected")


def test_validate_invite_link_returns_valid_true_for_active_token(monkeypatch):
    users_module = load_users_module(monkeypatch)

    invite = SimpleNamespace(invite_type="link", is_active=True)
    db = FakeDB([FakeQuery(first_result=invite)])

    response = users_module.validate_invite_link(
        data=users_module.schemas.InviteTokenValidateRequest(invite_token="raw-token"),
        db=db,
    )

    assert response.valid is True
    assert response.message is None


def test_validate_invite_link_returns_invalid_message_for_used_or_unknown_token(monkeypatch):
    users_module = load_users_module(monkeypatch)

    db = FakeDB([FakeQuery(first_result=None)])

    response = users_module.validate_invite_link(
        data=users_module.schemas.InviteTokenValidateRequest(invite_token="bad-token"),
        db=db,
    )

    assert response.valid is False
    assert response.message == users_module.INVALID_INVITE_MESSAGE


def test_onboard_with_valid_link_invite_consumes_invite(monkeypatch):
    users_module = load_users_module(monkeypatch)
    fake_clerk_user = make_clerk_user("doctor@example.com")
    users_module.clerk = SimpleNamespace(users=SimpleNamespace(get=lambda user_id: fake_clerk_user))

    invite = SimpleNamespace(
        invite_type="link",
        is_active=True,
        used_by_clerk_id=None,
        used_by_email=None,
        used_at=None,
    )
    db = FakeDB(
        [
            FakeQuery(first_result=None),
            FakeQuery(first_result=invite),
        ]
    )

    response = users_module.onboard_user(
        data=users_module.schemas.OnboardUserRequest(
            doctor_id="D-1",
            city="Mumbai",
            state="MH",
            experience=6,
            specialization="Cardiology",
            hospital="General Hospital",
            invite_token="raw-token",
        ),
        payload={"sub": "clerk_123"},
        db=db,
    )

    created_user = db.added[0]

    assert response["message"] == "User created"
    assert created_user.clerk_id == "clerk_123"
    assert invite.used_by_clerk_id == "clerk_123"
    assert invite.used_by_email == "doctor@example.com"
    assert invite.is_active is False
    assert invite.used_at is not None


def test_onboard_rejects_invalid_link_invite(monkeypatch):
    users_module = load_users_module(monkeypatch)
    fake_clerk_user = make_clerk_user("doctor@example.com")
    users_module.clerk = SimpleNamespace(users=SimpleNamespace(get=lambda user_id: fake_clerk_user))

    db = FakeDB(
        [
            FakeQuery(first_result=None),
            FakeQuery(first_result=None),
        ]
    )

    try:
        users_module.onboard_user(
            data=users_module.schemas.OnboardUserRequest(
                experience=6,
                specialization="Cardiology",
                invite_token="bad-token",
            ),
            payload={"sub": "clerk_123"},
            db=db,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == users_module.INVALID_INVITE_MESSAGE
    else:
        raise AssertionError("Expected invalid link invite to be rejected")


def test_onboard_still_supports_email_allowlist(monkeypatch):
    users_module = load_users_module(monkeypatch)
    fake_clerk_user = make_clerk_user("doctor@example.com")
    users_module.clerk = SimpleNamespace(users=SimpleNamespace(get=lambda user_id: fake_clerk_user))

    invite = SimpleNamespace(
        invite_type="email",
        is_active=True,
        used_by_clerk_id=None,
        used_by_email=None,
        used_at=None,
    )
    db = FakeDB(
        [
            FakeQuery(first_result=None),
            FakeQuery(first_result=invite),
        ]
    )

    response = users_module.onboard_user(
        data=users_module.schemas.OnboardUserRequest(
            experience=10,
            specialization="Neurology",
        ),
        payload={"sub": "clerk_456"},
        db=db,
    )

    assert response["message"] == "User created"
    assert invite.used_by_clerk_id == "clerk_456"
    assert invite.is_active is False
