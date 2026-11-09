"""Web layer: login, page delivery, upload, delete, and question routes."""
import os
import secrets
import time
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from .ingestion import MAX_UPLOAD, ingest
from .storage import list_documents, remove_document
from .retrieval import CHAT_MODEL, EMBED_MODEL, answer, ollama
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = os.getenv("RAG_PASSWORD", "")
failed_logins = {}
def authorized(request: Request, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    now = time.monotonic()
    address = request.client.host if request.client else "unknown"
    recent = [stamp for stamp in failed_logins.get(address, []) if now - stamp < 600]
    failed_logins[address] = recent
    if len(recent) >= 10:
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in 10 minutes.")
    good_user = secrets.compare_digest(credentials.username.encode(), b"rag")
    good_pass = secrets.compare_digest(credentials.password.encode(), PASSWORD.encode())
    if not PASSWORD or not (good_user and good_pass):
        failed_logins[address].append(now)
        raise HTTPException(401, "Incorrect username or password",
                            headers={"WWW-Authenticate": 'Basic realm="Simple Private RAG"'})
    failed_logins.pop(address, None)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(authorized)])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("RAG_HOST", "127.0.0.1,localhost").split(","))
@app.middleware("http")
async def headers(request, call_next):
    size = request.headers.get("content-length")
    if request.url.path == "/upload" and size and (not size.isdecimal() or int(size) > MAX_UPLOAD + 128_000):
        return JSONResponse(status_code=413, content={"detail": "Upload exceeds the 8 MB limit."})
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host')}"
        if origin != expected:
            return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:"
    response.headers["Cache-Control"] = "no-store"
    return response
@app.get("/")
@app.get("/static/{name}")
def static_file(name: str = "index.html"):
    if name not in {"index.html", "style.css", "app.js"}:
        raise HTTPException(404)
    return FileResponse(ROOT / "frontend" / name)
@app.get("/health")
def health():
    try:
        tags = ollama("/api/tags", method="GET")
        models = {m["name"] for m in tags.get("models", [])}
        return {"ok": True, "chat_model": CHAT_MODEL in models or f"{CHAT_MODEL}:latest" in models,
                "embedding_model": EMBED_MODEL in models or f"{EMBED_MODEL}:latest" in models}
    except HTTPException:
        return {"ok": False, "chat_model": False, "embedding_model": False}
@app.get("/documents")
def documents():
    return list_documents()
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload").name
    if Path(filename).suffix.lower() != ".txt":
        raise HTTPException(400, "Only TXT files are supported.")
    data = await file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(400, "File must be non-empty and no larger than 8 MB.")
    try:
        return ingest(filename, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    return remove_document(doc_id)
class Question(BaseModel):
    question: str
@app.post("/ask")
def ask(payload: Question):
    question = payload.question.strip()
    if not question or len(question) > 2000:
        raise HTTPException(400, "Question must be between 1 and 2000 characters.")
    return answer(question)
