"""最小可运行的 Web demo：FastAPI + 单页前端。"""
from __future__ import annotations

from pathlib import Path

import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from data_ingest import terrain
from pipeline import run_pipeline

# 简单限流：同一 IP 60 秒内只允许一次评估（防刷 + 省上游配额）
_RATE: dict[str, float] = {}
_RATE_WINDOW = 60.0

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
def assess(req: AssessRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    last = _RATE.get(ip, 0)
    if now - last < _RATE_WINDOW:
        wait = int(_RATE_WINDOW - (now - last)) + 1
        return JSONResponse(
            {"error": f"操作太频繁，请 {wait} 秒后再试（每 60 秒可评估一次）",
             "retry_after": wait}, status_code=429)
    _RATE[ip] = now
    try:
        result = run_pipeline(req.address)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
