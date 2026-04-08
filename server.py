"""
FastAPI server for the RAG Document Assistant.

Run with:
    uvicorn server:app --reload
"""

import json
import sqlite3
import tempfile
import os
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag_agent import RAGAgent

app = FastAPI(title="RAG Document Assistant")
agent = RAGAgent()

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "conversations.db"


# Database
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


init_db()


@app.get("/")
def index():
    return FileResponse("static/index.html")


# Documents

@app.post("/upload")
async def upload(file: UploadFile = File(...), conversation_id: int | None = Form(None)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Auto-create a conversation if none is active
    if conversation_id is None:
        now = datetime.now(timezone.utc).isoformat()
        title = file.filename
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
                (title, now),
            )
            conn.commit()
            conversation_id = cur.lastrowid

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        chunks = agent.upload_pdf(tmp_path, source_name=file.filename, conversation_id=conversation_id)
    finally:
        os.unlink(tmp_path)

    return {"filename": file.filename, "chunks": chunks, "conversation_id": conversation_id}


@app.get("/documents")
def list_documents(conversation_id: int | None = None):
    return {"documents": agent.list_documents(conversation_id=conversation_id)}


@app.delete("/documents/{name:path}")
def delete_document(name: str, conversation_id: int | None = None):
    deleted = agent.delete_document(name, conversation_id=conversation_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found.")
    return {"deleted": deleted}


# Conversations

K_BY_MODE = {"search": 20, "summarize": 100}

class AskRequest(BaseModel):
    question: str
    conversation_id: int | None = None
    mode: str = "search"  # "search" | "summarize"


@app.get("/conversations")
def list_conversations():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversations ORDER BY id DESC"
        ).fetchall()
    return {"conversations": [dict(r) for r in rows]}


@app.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: int):
    with get_db() as conn:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        rows = conn.execute(
            "SELECT role, content, sources FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()
    messages = []
    for r in rows:
        msg = {"role": r["role"], "content": r["content"]}
        if r["sources"]:
            msg["sources"] = json.loads(r["sources"])
        messages.append(msg)
    return {"messages": messages}


@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conv_id,)
        )
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    agent.delete_conversation_documents(conv_id)
    return {"deleted": conv_id}


# Query
@app.post("/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    now = datetime.now(timezone.utc).isoformat()

    # Create or reuse conversation
    with get_db() as conn:
        if req.conversation_id is None:
            title = req.question[:60].strip()
            cur = conn.execute(
                "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
                (title, now),
            )
            conn.commit()
            conv_id = cur.lastrowid
        else:
            row = conn.execute(
                "SELECT id FROM conversations WHERE id = ?", (req.conversation_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            conv_id = req.conversation_id

        # Persist user message
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, NULL, ?)",
            (conv_id, "user", req.question, now),
        )
        conn.commit()

    answer_parts: list[str] = []
    final_sources: list[str] = []

    def generate():
        nonlocal answer_parts, final_sources

        # Emit conversation_id first so the client can track it
        yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}\n\n"

        k = K_BY_MODE.get(req.mode, K_BY_MODE["search"])
        for event in agent.stream_query(req.question, k=k, conversation_id=conv_id):
            yield f"data: {json.dumps(event)}\n\n"

            if event["type"] == "chunk":
                answer_parts.append(event["text"])
            elif event["type"] == "done":
                final_sources = event.get("sources", [])

        # Persist assistant message
        full_answer = "".join(answer_parts)
        sources_json = json.dumps(final_sources) if final_sources else None
        save_now = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, "assistant", full_answer, sources_json, save_now),
            )
            conn.commit()

    return StreamingResponse(generate(), media_type="text/event-stream")
