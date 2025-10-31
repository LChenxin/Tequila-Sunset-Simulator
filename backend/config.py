# backend/config.py
from __future__ import annotations
import os
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [x.strip() for x in raw.split(",") if x.strip()]

class Settings:
    """App settings for FastAPI + single-skill agent (PoC)."""

    # --- API ---
    API_TITLE: str = os.getenv("API_TITLE", "Tequila Sunset Simulator (PoC)")
    API_VERSION: str = os.getenv("API_VERSION", "0.1.0")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # --- CORS ---
    # 多域名用逗号分隔：CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:5173"
    CORS_ORIGINS: List[str] = _env_list("CORS_ORIGINS", ["*"])

    # --- LLM / Inference ---
    # 是否尝试走 HelloAgents（缺包或异常会在 agents.py 内自动降级）
    HELLOAGENTS_ENABLED: bool = _env_bool("HELLOAGENTS_ENABLED", True)

    # OpenAI 兼容（给回退路径用；有 API_KEY 才会真实调用，否则 Echo）
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    API_KEY: Optional[str] = os.getenv("API_KEY") or os.getenv("LLM_API_KEY")
    BASE_URL: str = os.getenv("BASE_URL", "https://api.openai.com/v1")

    # 未提供 API_KEY 时是否允许 Echo 回退（仅影响日志提示）
    ECHO_FALLBACK_ALLOWED: bool = _env_bool("ECHO_FALLBACK_ALLOWED", True)

    # --- Memory (PoC) ---
    WORKING_MEMORY_CAPACITY: int = int(os.getenv("WORKING_MEMORY_CAPACITY", "10"))
    WORKING_MEMORY_TOKENS: int = int(os.getenv("WORKING_MEMORY_TOKENS", "2000"))
    EPISODIC_MEMORY_CAPACITY: int = int(os.getenv("EPISODIC_MEMORY_CAPACITY", "100"))
    ENABLE_FORGETTING: bool = _env_bool("ENABLE_FORGETTING", True)
    FORGETTING_THRESHOLD: float = float(os.getenv("FORGETTING_THRESHOLD", "0.3"))

    def validate(self) -> bool:
        print("🧰 Config summary")
        print(f"  • API_TITLE     : {self.API_TITLE}")
        print(f"  • API_VERSION   : {self.API_VERSION}")
        print(f"  • API_HOST:PORT : {self.API_HOST}:{self.API_PORT}")
        print(f"  • CORS_ORIGINS  : {self.CORS_ORIGINS}")
        print(f"  • HELLOAGENTS   : {'enabled' if self.HELLOAGENTS_ENABLED else 'disabled'}")
        print(f"  • MODEL_NAME    : {self.MODEL_NAME}")
        print(f"  • BASE_URL      : {self.BASE_URL}")
        if not self.API_KEY:
            if self.ECHO_FALLBACK_ALLOWED:
                print("⚠️  未检测到 API_KEY，将使用 Echo 回退以便本地联调。")
            else:
                print("⚠️  未检测到 API_KEY，且不允许 Echo 回退，可能无法生成内容。")
        else:
            print("✅ 已检测到 API_KEY。")
        print("🧠 Memory config")
        print(f"  • working_cap   : {self.WORKING_MEMORY_CAPACITY} (tokens={self.WORKING_MEMORY_TOKENS})")
        print(f"  • episodic_cap  : {self.EPISODIC_MEMORY_CAPACITY}")
        print(f"  • forgetting    : {self.ENABLE_FORGETTING} (threshold={self.FORGETTING_THRESHOLD})")
        return True

settings = Settings()
