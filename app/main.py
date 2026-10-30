import json, os, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
from .db import connect, initialize

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield

app = FastAPI(title="CodeJudge", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Submission(BaseModel):
    language: str
    source: str = Field(min_length=1, max_length=50000)
    stdin: str = Field(default="", max_length=10000)
    expected_output: str = Field(default="", max_length=10000)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/submissions", status_code=202)
def submit(payload: Submission):
    if payload.language not in {"python", "javascript", "java", "cpp"}:
        raise HTTPException(400, "language must be python, javascript, java, or cpp")
    sid = str(uuid.uuid4())
    with connect() as conn:
        conn.execute("INSERT INTO submissions(id,language,source,stdin,expected,status) VALUES (%s,%s,%s,%s,%s,'queued')",
                     (sid, payload.language, payload.source, payload.stdin, payload.expected_output))
    redis.rpush("judge:queue", sid)
    return {"id": sid, "status": "queued", "status_url": f"/submissions/{sid}"}

@app.get("/submissions")
def list_submissions():
    with connect() as conn:
        rows = conn.execute("SELECT id,language,status,result,created_at,finished_at FROM submissions ORDER BY created_at DESC LIMIT 100").fetchall()
    return rows

@app.get("/submissions/{sid}")
def get_submission(sid: str):
    with connect() as conn:
        row = conn.execute("SELECT id,language,status,result,created_at,finished_at FROM submissions WHERE id=%s", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, "submission not found")
    return row
