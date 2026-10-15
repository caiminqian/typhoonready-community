"""最小可运行的 Web demo：FastAPI + 单页前端。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from data_ingest import terrain
from pipeline import run_pipeline

app = FastAPI(title="AI4Climate Track05 原型：台风-内涝社区韧性指引")
STATIC_DIR = Path(__file__).resolve().parent / "static"


class AssessRequest(BaseModel):
    address: str


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/communities")
def communities():
    return {"communities": terrain.list_communities()}


@app.post("/api/assess")
def assess(req: AssessRequest):
    try:
        result = run_pipeline(req.address)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
