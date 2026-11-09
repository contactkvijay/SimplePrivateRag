"""SQLite storage and passage ranking."""
import os
import re
import sqlite3
import uuid
import numpy as np
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
DATA = Path(os.getenv("RAG_DATA_DIR", Path.home() / ".local/share/simple-private-rag"))
FILES = DATA / "files"
DB = DATA / "rag.sqlite3"
@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    DATA.chmod(0o700)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    # documents holds file details; chunks holds passages and their vectors.
    db.executescript("""
      CREATE TABLE IF NOT EXISTS documents(
        id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored TEXT NOT NULL,
        uploaded TEXT NOT NULL, status TEXT NOT NULL, embedding_model TEXT NOT NULL,
        embedding_dimensions INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS chunks(
        id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        position INTEGER NOT NULL, content TEXT NOT NULL, reference TEXT NOT NULL,
        embedding BLOB NOT NULL, UNIQUE(document_id, position));
    """)
    with closing(db), db:
        yield db
def list_documents():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id, filename, uploaded, status FROM documents ORDER BY uploaded DESC")]
def delete_document(db, document_id):
    row = db.execute("SELECT stored FROM documents WHERE id=?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found.")
    # Foreign-key cascade also deletes every chunk for this document.
    db.execute("DELETE FROM documents WHERE id=?", (document_id,))
    return FILES / row["stored"]
def remove_document(document_id):
    with connect() as db:
        saved_file = delete_document(db, document_id)
    saved_file.unlink(missing_ok=True)
    return {"deleted": True}
def save_document(filename, data, passages, vectors, model):
    old_files = []
    doc_id = uuid.uuid4().hex
    stored = doc_id + ".txt"
    FILES.mkdir(parents=True, exist_ok=True, mode=0o700)
    FILES.chmod(0o700)
    (FILES / stored).write_bytes(data)
    try:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute("SELECT id FROM documents WHERE filename=?", (filename,)).fetchall():
                old_files.append(delete_document(db, row["id"]))
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
                       (doc_id, filename, stored, datetime.now(timezone.utc).isoformat(),
                        "ready", model, len(vectors[0])))
            for i, (text, reference) in enumerate(passages):
                db.execute("INSERT INTO chunks(document_id,position,content,reference,embedding) VALUES(?,?,?,?,?)",
                           (doc_id, i, text, reference, vectors[i].tobytes()))
    except Exception:
        (FILES / stored).unlink(missing_ok=True)
        raise
    for old_file in old_files:
        old_file.unlink(missing_ok=True)
    return {"id": doc_id, "filename": filename, "status": "ready"}
def find_similar_passages(question_vector, model, question="", keyword_weight=0.35):
    with connect() as db:
        rows = db.execute("""SELECT c.content,c.reference,d.filename,c.embedding,d.embedding_dimensions
            FROM chunks c JOIN documents d ON d.id=c.document_id
            WHERE d.status='ready' AND d.embedding_model=?""", (model,)).fetchall()
    if not rows:
        raise HTTPException(400, "Upload a document before asking a question.")
    ranked = []
    ignored = set("what who where when is are the a an my me for of in and please show list give details number s".split())
    question_words = set(re.findall(r"[a-z0-9]+", question.lower().replace("'s", ""))) - ignored
    for row in rows:
        vector = np.frombuffer(row["embedding"], dtype=np.float32)
        if len(vector) != row["embedding_dimensions"] or len(question_vector) != len(vector):
            continue
        vector_lengths = np.linalg.norm(question_vector) * np.linalg.norm(vector)
        if vector_lengths:
            # Cosine similarity: a higher score means a closer meaning.
            score = float(np.dot(question_vector, vector) / vector_lengths)
            passage_words = set(re.findall(r"[a-z0-9]+", row["content"].lower()))
            word_score = len(question_words & passage_words) / max(len(question_words), 1)
            score = (1 - keyword_weight) * score + keyword_weight * word_score
            ranked.append((score, row))
    if not ranked:
        raise HTTPException(400, "No documents match the current embedding model. Re-upload them after changing models.")
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [dict(passage) for score, passage in ranked[:5]]
