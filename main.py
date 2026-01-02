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

# --- БД ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./notes.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NoteDB(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    category = Column(String, default="Разное") # Добавили колонку категории
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m %H:%M"))

Base.metadata.create_all(bind=engine)

# --- APP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Схемы данных
class NoteCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = "Разное" # Добавили в схему

class NoteResponse(NoteCreate):
    id: int
    created_at: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- МАРШРУТЫ ---

@app.get("/notes/", response_model=List[NoteResponse])
def get_notes(db: Session = Depends(get_db)):
    return db.query(NoteDB).all()

@app.post("/notes/", response_model=NoteResponse)
def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    # Теперь сохраняем и категорию тоже
    new_note = NoteDB(title=note.title, content=note.content, category=note.category)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note

@app.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(NoteDB).filter(NoteDB.id == note_id).first()
    if not note: raise HTTPException(status_code=404)
    db.delete(note)
    db.commit()
    return {"status": "deleted"}

# НОВЫЙ МАРШРУТ: Экспорт в TXT
@app.get("/export")
def export_notes(db: Session = Depends(get_db)):
    notes = db.query(NoteDB).all()
    
    # Формируем текстовое содержимое
    report = "=== МОИ ЗАМЕТКИ (BACKUP) ===\n\n"
    for n in notes:
        report += f"Дата: {n.created_at} | Категория: {n.category}\n"
        report += f"Заголовок: {n.title}\n"
        report += f"Текст: {n.content}\n"
        report += "-"*30 + "\n\n"
    
    # Отправляем как файл для скачивания
    file_stream = io.BytesIO(report.encode("utf-8"))
    return StreamingResponse(
        file_stream,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=notes_backup.txt"}
    )