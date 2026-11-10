
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.db import get_db, Base, engine
from app.api import auth as auth_api
from app.api import projects as projects_api
from app.api import tasks as tasks_api
from app.api import tasks_update as tasks_update_api
from app.api import members as members_api
from app.api import members_manage as members_manage_api
from app.api import tasks_archive as tasks_archive_api
from app.api import subtasks as subtasks_api

from app.core.exception import register_exception_handler

app = FastAPI()
register_exception_handler(app)
app.include_router(auth_api.router)
app.include_router(projects_api.router)
app.include_router(tasks_api.router)
app.include_router(tasks_update_api.router)
app.include_router(members_api.router)
app.include_router(members_manage_api.router)
app.include_router(tasks_archive_api.router)
app.include_router(subtasks_api.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

Base.metadata.create_all(bind=engine)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/health/db")
def check_database(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "success",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(e)
        }
