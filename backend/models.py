# backend/models.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -------------------- Requests --------------------
class StepRequest(BaseModel):
    """
    /v1/step 的请求体：
    - user_text: 玩家（或前端）传入的感知文本
    - session_id: 会话标识（可选，不传则使用 'default'）
    """
    user_text: str = Field(..., description="Perception text from user/front-end")
    session_id: Optional[str] = Field(None, description="Session ID (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "user_text": "The neon blinks twice, like a tired eye.",
                "session_id": "demo-001"
            }
        }


class ResetRequest(BaseModel):
    """
    /v1/reset 的请求体：
    - session_id: 要重置的会话（可选，不传则重置默认会话）
    """
    session_id: Optional[str] = Field(None, description="Session ID to reset")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "demo-001"
            }
        }


# -------------------- Responses --------------------
class StepResponse(BaseModel):
    """
    /v1/step 的响应体：
    - 返回 Inland Empire 的 1-2 行内心独白与渲染文本等
    """
    session_id: str = Field(..., description="Session ID")
    turn: int = Field(..., description="Turn index for this session")
    speaker: str = Field(..., description="Skill/agent speaker name (e.g., 'Inland Empire')")
    primary: str = Field(..., description="Primary inner monologue (1–2 short lines)")
    chorus: List[str] = Field(default_factory=list, description="(PoC) reserved for future multi-voice outputs")
    narration: Optional[str] = Field(None, description="(PoC) reserved for narrator text")
    mood: Dict[str, Any] = Field(default_factory=dict, description="(PoC) reserved for mood signals")
    rendered: str = Field(..., description="Plain-text rendering for immediate display")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "demo-001",
                "turn": 3,
                "speaker": "Inland Empire",
                "primary": "Something moves behind the curtain—no wind, just intent.",
                "chorus": [],
                "narration": None,
                "mood": {},
                "rendered": "— TURN 3 —\nINLAND EMPIRE: Something moves behind the curtain—no wind, just intent."
            }
        }


class StateSnapshot(BaseModel):
    """
    /v1/state 的响应体：
    - 当前回合数、共享记忆快照以及按技能归档的记忆（PoC 简化为同一套）
    """
    session_id: str = Field(..., description="Session ID")
    turn: int = Field(..., description="Current turn index")
    mood: Dict[str, Any] = Field(default_factory=dict, description="(PoC) reserved for mood signals")
    shared_trace: List[Any] = Field(default_factory=list, description="Recent memory items for quick HUD display")
    agents: Dict[str, Any] = Field(default_factory=dict, description="Per-agent memory/trace (PoC simplified)")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "demo-001",
                "turn": 5,
                "mood": {},
                "shared_trace": [
                    {"content": "PERCEPTION: The neon blinks twice.", "type": "working", "timestamp": None},
                    {"content": "INLAND EMPIRE: The sign wants to speak.", "type": "working", "timestamp": None}
                ],
                "agents": {
                    "Inland Empire": [
                        {"content": "PERCEPTION: The neon blinks twice.", "type": "working"},
                        {"content": "INLAND EMPIRE: The sign wants to speak.", "type": "working"}
                    ]
                }
            }
        }
