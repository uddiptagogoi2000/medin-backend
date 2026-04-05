from datetime import datetime
from typing import Dict, Any, List, Literal, Optional

from pydantic import BaseModel, Field

class PostCreate(BaseModel):
    title: str
    content: Dict[str, Any]
    visibility: str
    is_anonymous: bool
    tags: List[str] = Field(default_factory=list)

class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    visibility: Optional[str] = None
    is_anonymous: Optional[bool] = None
    tags: Optional[List[str]] = None

class PostResponse(BaseModel):
    id: int
    title: str
    content: Dict[str, Any]
    preview_text: Optional[str]
    first_image: Optional[str]
    tags: List[str] = Field(default_factory=list)
    visibility: str
    is_anonymous: bool
    author_clerk_id: str

    class Config:
        from_attributes = True

class PostFeedResponse(BaseModel):
    id: int
    title: str
    content: Dict[str, Any]
    preview_text: Optional[str]
    first_image: Optional[str]
    tags: List[str] = Field(default_factory=list)
    visibility: str
    is_anonymous: bool
    author_clerk_id: str
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    author_specialization: Optional[str] = None
    author_hospital: Optional[str] = None
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    is_liked_by_me: bool = False
    is_reposted_by_me: bool = False
    is_following_author: bool = False

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    content: dict

class CommentUpdate(BaseModel):
    content: dict

class CommentAuthor(BaseModel):
    clerk_id: str
    name: str
    avatar: Optional[str] = None
    specialization: Optional[str] = None
    hospital: Optional[str] = None

class CommentResponse(BaseModel):
    id: int
    post_id: int
    content: dict
    created_at: datetime
    author: CommentAuthor
    class Config:
        orm_mode = True

class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    has_more: bool

    class Config:
        orm_mode = True

class SuggestedDoctor(BaseModel):
    clerk_id: str
    name: Optional[str]
    avatar: Optional[str]
    specialization: Optional[str]
    hospital: Optional[str]
    city: Optional[str]
    experience: Optional[int]
    is_following: bool = False

from pydantic import BaseModel
from typing import Optional
from datetime import date

class ProfileBasicUpdate(BaseModel):
    city: Optional[str]
    state: Optional[str]
    experience: Optional[int]
    specialization: Optional[str]
    hospital: Optional[str]

class ProfileAboutUpdate(BaseModel):
    about: Optional[str]

class ExperienceCreate(BaseModel):
    position: str
    organization: str
    start_date: date
    end_date: Optional[date] = None
    is_current: Optional[bool] = False
    description: Optional[str] = None


class ExperienceUpdate(ExperienceCreate):
    pass

class EducationCreate(BaseModel):
    degree: str
    institution: str
    start_year: int
    end_year: Optional[int] = None

class EducationUpdate(EducationCreate):
    pass

class PublicationCreate(BaseModel):
    title: str
    journal: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None
    doi: Optional[str] = None


class PublicationUpdate(PublicationCreate):
    pass

class ProfileIdentityUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SearchUserResult(BaseModel):
    clerk_id: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    doctor_id: Optional[str] = None
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class SearchPostResult(BaseModel):
    id: int
    title: str
    preview_text: Optional[str] = None
    first_image: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    visibility: str
    is_anonymous: bool
    author_clerk_id: str
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    created_at: datetime


class GlobalSearchResponse(BaseModel):
    query: str
    users: List[SearchUserResult]
    posts: List[SearchPostResult]


class EngagementPromptResponse(BaseModel):
    id: int
    title: str
    body: str
    suggested_tags: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PromptEventCreate(BaseModel):
    event_type: Literal["shown", "dismissed", "clicked_post", "posted"]


class InviteCheckRequest(BaseModel):
    email: str
