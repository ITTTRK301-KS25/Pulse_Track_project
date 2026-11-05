from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.db import get_db, Base, engine

app = FastAPI()

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