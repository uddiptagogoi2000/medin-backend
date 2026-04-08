from fastapi import FastAPI
from app.routers import connections, engagement, follows, posts, profile, search, upload, users
from app.database import engine, Base
from app import models
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://medin-frontend.vercel.app",
    "https://serona.co.in",
    "https://www.serona.co.in",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(upload.router)
app.include_router(posts.router)
app.include_router(engagement.router)
app.include_router(follows.router)
app.include_router(connections.router)
app.include_router(profile.router)
app.include_router(search.router)

@app.get("/")
def root():
    return {"message": "API running"}
