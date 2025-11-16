# backend/main.py
from __future__ import annotations

from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models import StepRequest, StepResponse, ResetRequest, StateSnapshot
from agents import InlandEmpireAgent


# -------------------- Lifespan --------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 60)
    print("🌀 Tequila Sunset Simulator (PoC) — Inland Empire only")
    print("=" * 60)

    if hasattr(settings, "validate"):
        try:
            settings.validate()
        except Exception as e:
            print(f"⚠️ settings.validate() failed: {e}")

    # 初始化单技能 Agent 与回合计数器
    app.state.agent = InlandEmpireAgent()
    app.state.turns = defaultdict(int)  # session_id -> turn

    print("\n✅ Service started!")
    print(f"📡 API:   http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📚 Docs:  http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print("=" * 60 + "\n")
    try:
        yield
    finally:
        pass  # PoC 无需清理


# -------------------- App & CORS --------------------
app = FastAPI(
    title=getattr(settings, "API_TITLE", "Tequila Sunset Simulator (PoC)"),
    version=getattr(settings, "API_VERSION", "0.1.0"),
    description="Disco Elysium–style inner monologue (Inland Empire only)",
    lifespan=lifespan,
)

cors_origins = getattr(settings, "CORS_ORIGINS", ["*"])
allow_credentials = True
if "*" in cors_origins:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------- Routes --------------------
@app.get("/")
async def root():
    return {
        "service": app.title,
        "version": app.version,
        "status": "running",
        "features": ["inner monologue (Inland Empire)"],
        "endpoints": {
            "health": "/health",
            "step": "/v1/step",
            "reset": "/v1/reset",
            "state": "/v1/state",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/v1/step", response_model=StepResponse)
async def step(req: StepRequest):
    """
    单回合：输入文本 → Inland Empire 的 1–2 行内心独白。
    """
    # 基础校验
    if not req.user_text or not str(req.user_text).strip():
        raise HTTPException(status_code=400, detail="user_text is required")

    MAX_LEN = 4000
    user_text = str(req.user_text)
    if len(user_text) > MAX_LEN:
        user_text = user_text[:MAX_LEN]

    session_id = req.session_id or "default"
    app.state.turns[session_id] += 1
    turn = app.state.turns[session_id]

    try:
        duo = await app.state.agent.speak_duo(user_text)
        primary = (duo.get("primary") or "").strip()
        logic_line = (duo.get("logic") or "").strip()
        if not primary:
            primary = "A hunch glints and is gone—like light on a broken bottle."
    except Exception as e:
        print(f"⚠️ agent.speak_duo failed: {e}")
        primary = "A cold intuition passes—like a draft under a locked door."
        logic_line = ""

    # 组装合唱
    chorus = []
    if logic_line:
        chorus.append(f"LOGIC: {logic_line}")

    # 渲染（前端可直接展示）
    rendered_lines = [f"— TURN {turn} —", f"INLAND EMPIRE: {primary}"]
    if logic_line:
        rendered_lines.append(f"LOGIC: {logic_line}")
    rendered = "\n".join(rendered_lines)

    return StepResponse(
        session_id=session_id,
        turn=turn,
        speaker="Inland Empire",
        primary=primary,
        chorus=chorus,
        narration=None,
        mood={},              # 之后可以在这里放情绪
        rendered=rendered,
    )

@app.post("/v1/reset")
async def reset(req: ResetRequest):
    """
    重置会话：回合清零 + 清空记忆
    """
    session_id = req.session_id or "default"
    app.state.turns[session_id] = 0
    try:
        app.state.agent.clear_memory()
    except Exception as e:
        print(f"⚠️ clear_memory failed: {e}")
    return {"ok": True, "session_id": session_id}


@app.get("/v1/state", response_model=StateSnapshot)
async def state(session_id: Optional[str] = "default"):
    """
    返回当前回合号与最近记忆（用于前端侧栏/HUD 调试）
    """
    sid = session_id or "default"
    turn = app.state.turns[sid]
    # 这里把 agent 的记忆作为 shared_trace 暂时返回（PoC 简化）
    try:
        shared_trace = app.state.agent.get_memories(limit=12)
    except Exception as e:
        print(f"⚠️ get_memories failed: {e}")
        shared_trace = []

    agents = {"Inland Empire": shared_trace}  # 与模型字段保持一致的简化结构

    return StateSnapshot(
        session_id=sid,
        turn=turn,
        mood={},  # PoC：先空
        shared_trace=shared_trace,
        agents=agents,
    )


# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    print("\n🚀 Starting Tequila Sunset Simulator (PoC)...")
    host = getattr(settings, "API_HOST", "0.0.0.0")
    port = int(getattr(settings, "API_PORT", 8000))
    print(f"📍 http://{host}:{port}\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
