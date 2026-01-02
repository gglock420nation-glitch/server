from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import io

# --- Настройка БД ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./notes.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NoteDB(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    category = Column(String, default="Разное")
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m %H:%M"))

Base.metadata.create_all(bind=engine)

# --- Приложение ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class NoteCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = "Разное"

class NoteResponse(NoteCreate):
    id: int
    created_at: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Маршруты ---

@app.get("/")
def home():
    return {"status": "Online", "msg": "API is working. Use /notes/ or /export"}

@app.get("/notes/", response_model=List[NoteResponse])
def get_notes(db: Session = Depends(get_db)):
    return db.query(NoteDB).all()

@app.post("/notes/", response_model=NoteResponse)
def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    new_note = NoteDB(title=note.title, content=note.content, category=note.category)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note

@app.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(NoteDB).filter(NoteDB.id == note_id).first()
    if not note: 
        raise HTTPException(status_code=404)
    db.delete(note)
    db.commit()
    return {"status": "deleted"}

@app.get("/export")
def export_notes(db: Session = Depends(get_db)):
    notes = db.query(NoteDB).all()
    report = "=== MY DASHBOARD BACKUP ===\n\n"
    for n in notes:
        report += f"[{n.created_at}] {n.category} | {n.title}\n{n.content}\n{'-'*30}\n"
    
    return StreamingResponse(
        io.BytesIO(report.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=notes_backup.txt"}
    )