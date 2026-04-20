from sqlalchemy import Column, Date, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clerk_id = Column(String, unique=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    doctor_id = Column(String)
    city = Column(String)
    state = Column(String)
    experience = Column(Integer)
    specialization = Column(String)
    hospital = Column(String)
    about = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)

    content = Column(JSONB, nullable=False)   # Full TipTap JSON

    preview_text = Column(Text, nullable=True)
    first_image = Column(String, nullable=True)
    tags = Column(ARRAY(String), nullable=False, default=list)

    visibility = Column(String, default="public")
    is_anonymous = Column(Boolean, default=False)

    author_clerk_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    comments = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan"
    )

    likes = relationship(
        "Like",
        cascade="all, delete-orphan"
    )

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    user_clerk_id = Column(String, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("post_id", "user_clerk_id", name="unique_post_like"),
    )

class Repost(Base):
    __tablename__ = "reposts"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    user_clerk_id = Column(String, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("post_id", "user_clerk_id", name="unique_post_repost"),
    )

class EngagementPrompt(Base):
    __tablename__ = "engagement_prompts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    suggested_tags = Column(ARRAY(String), nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserPromptEvent(Base):
    __tablename__ = "user_prompt_events"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("engagement_prompts.id", ondelete="CASCADE"), nullable=False)
    user_clerk_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    token_hash = Column(String, unique=True, nullable=True, index=True)
    invite_type = Column(String, nullable=False, default="email", index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    used_by_clerk_id = Column(String, nullable=True, index=True)
    used_by_email = Column(String, nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    author_clerk_id = Column(String, index=True, nullable=False)
    content = Column(JSONB, nullable=False)  # Full TipTap JSON

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("Post", back_populates="comments")

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)

    follower_clerk_id = Column(String, index=True)   # who follows
    following_clerk_id = Column(String, index=True)  # who is being followed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "follower_clerk_id",
            "following_clerk_id",
            name="unique_follow"
        ),
    )

class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True)
    user_clerk_id = Column(String, ForeignKey("users.clerk_id", ondelete="CASCADE"))

    position = Column(String)
    organization = Column(String)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Education(Base):
    __tablename__ = "educations"

    id = Column(Integer, primary_key=True)
    user_clerk_id = Column(String, ForeignKey("users.clerk_id", ondelete="CASCADE"))

    degree = Column(String)
    institution = Column(String)
    start_year = Column(Integer)
    end_year = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True)
    user_clerk_id = Column(String, ForeignKey("users.clerk_id", ondelete="CASCADE"))

    title = Column(String)
    journal = Column(String)
    year = Column(Integer)
    url = Column(String, nullable=True)
    doi = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
