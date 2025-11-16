from __future__ import annotations

import os
import re
import time
import textwrap
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import deque

from openai import AsyncOpenAI
from config import settings


# -------------------- Simple ring memory for fallback --------------------
class RingMemory:
    def __init__(self, maxlen: int = 8):
        self.buf = deque(maxlen=maxlen)

    def add(self, role: str, text: str):
        self.buf.append({"t": time.time(), "role": role, "text": text})

    def dump(self) -> List[Dict]:
        return list(self.buf)

    def fmt(self) -> str:
        if not self.buf:
            return "(no memory)"
        return "\n".join(f"[{x['role'].upper()}] {x['text']}" for x in self.buf)

    def clear(self):
        self.buf.clear()


# -------------------- Output sanitizer --------------------
GREET_RE = re.compile(r'^\s*(hi|hello|hey|greetings|bonjour|salut|你好|嗨)[,!\.\s-]*', re.I)

def sanitize_inner_monologue(text: str) -> str:
    t = (text or "").strip()
    t = GREET_RE.sub('', t).strip()
    if t.endswith('?') and '\n' not in t:
        t = t.rstrip(' ?！!。.') + '.'
    t = re.sub(r'[\.。!！…]{3,}', '…', t)
    t = re.sub(r'[*_`~#>\[\]{}()|]', '', t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return "\n".join(lines[:2])


# -------------------- Persona --------------------
DISCO_HEADER = (
    "You are an inner skill in a Disco Elysium–style mind-palace.\n"
    "This is inner monologue triggered by perception; NEVER address the player.\n"
    "1–2 short lines. No greetings. No questions. No emojis. No markdown.\n"
    "Write as thought, not conversation.\n"
)

INLAND_PERSONA = DISCO_HEADER + (
    "ROLE: INLAND EMPIRE — hunches, gut feelings, dream-logic in daylight. "
    "Voice is eerie, associative, instinctive. Speak in images and uncanny parallels.\n"
)

LOGIC_PERSONA = DISCO_HEADER + (
    "ROLE: LOGIC — clinical deduction, causal chains, consistency checks.\n"
    "VOICE: dry, surgical. Cite gaps, assumptions, counterfactuals. Disdain theatrics.\n"
    "PRIORITY: evidence > intuition. Flag uncertainty explicitly.\n"
)

# -------------------- OpenAI-compatible fallback --------------------
class FallbackLLM:
    """OpenAI-compatible async wrapper with echo fallback."""
    def __init__(self, model: str, api_key: Optional[str], base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.echo = not bool(api_key)
        self.client = None
        if not self.echo:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def acomplete(self, messages, temperature=0.8, max_tokens=160) -> str:
        # Echo
        if self.echo or self.client is None:
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return f"(ECHO) {last_user[:180]}"
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"⚠️ OpenAI-compatible call failed, fallback to echo: {e}")
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return f"(ECHO) {last_user[:180]}"


# -------------------- Agent --------------------
@dataclass
class InlandEmpireAgent:
    model_name: str = field(default_factory=lambda: settings.MODEL_NAME)
    api_key: Optional[str] = field(default_factory=lambda: settings.API_KEY)
    base_url: str = field(default_factory=lambda: settings.BASE_URL)
    hello_enabled: bool = field(default_factory=lambda: getattr(settings, "HELLOAGENTS_ENABLED", True))

    temperature: float = 0.95
    max_tokens: int = 140
    memory_dir: Optional[str] = None

    # runtime
    _hello: bool = field(init=False, default=False)
    _llm: Optional[object] = field(init=False, default=None)
    _agent: Optional[object] = field(init=False, default=None)        # HelloAgents.SimpleAgent
    _mem_mgr: Optional[object] = field(init=False, default=None)      # HelloAgents.MemoryManager
    _ring: Optional[RingMemory] = field(init=False, default=None)     # Fallback ring memory

    def __post_init__(self):
        self._hello = bool(self.hello_enabled)
        if self._hello:
            try:
                from hello_agents import SimpleAgent, HelloAgentsLLM
                from hello_agents.memory import MemoryManager, MemoryConfig

                self._llm = HelloAgentsLLM()  # 使用其内部环境配置
                self._agent = SimpleAgent(
                    name="Inland Empire",
                    llm=self._llm,
                    system_prompt=self._build_hello_system_prompt()
                )

                # Memory
                mem_dir = self.memory_dir or os.path.join(
                    os.path.dirname(__file__), "memory_data", "InlandEmpire"
                )
                os.makedirs(mem_dir, exist_ok=True)
                cfg = MemoryConfig(
                    storage_path=mem_dir,
                    working_memory_capacity=getattr(settings, "WORKING_MEMORY_CAPACITY", 10),
                    working_memory_tokens=getattr(settings, "WORKING_MEMORY_TOKENS", 2000),
                    episodic_memory_capacity=getattr(settings, "EPISODIC_MEMORY_CAPACITY", 100),
                    enable_forgetting=getattr(settings, "ENABLE_FORGETTING", True),
                    forgetting_threshold=getattr(settings, "FORGETTING_THRESHOLD", 0.3),
                )
                self._mem_mgr = MemoryManager(
                    config=cfg,
                    user_id="InlandEmpire",
                    enable_working=True, enable_episodic=True,
                    enable_semantic=False, enable_perceptual=False
                )
                print("✅ HelloAgents path enabled.")
                return
            except Exception as e:
                print(f"⚠️ HelloAgents init failed, fallback to OpenAI/Echo: {e}")
                self._hello = False

        # fallback
        self._llm = FallbackLLM(self.model_name, self.api_key, self.base_url)
        self._ring = RingMemory(8)
        print(f"ℹ️ Fallback path enabled. Echo={getattr(self._llm, 'echo', True)}")

    def _build_hello_system_prompt(self) -> str:
        return INLAND_PERSONA + textwrap.dedent("""
        [OUTPUT CONTRACT]
        - Thought triggered by PERCEPTION.
        - 1–2 short lines, inner monologue. No greetings, no questions.
        - Do not address the player directly.
        """).strip()

    def _build_logic_system_prompt(self) -> str:
        return LOGIC_PERSONA + textwrap.dedent("""
        [OUTPUT CONTRACT]
        - Analyze the perception with cold deduction.
        - Highlight gaps, assumptions, causal chains.
        - 1–2 short lines, inner monologue. No greetings, no questions.
        """).strip()
    
    def _build_user_context(self, user_text: str, trace_text: str = "") -> str:
        return textwrap.dedent(f"""
        [PERCEPTION]
        {user_text}

        [YOUR TRACE]
        {trace_text or "(no memory)"}

        [INSTRUCTIONS]
        Respond with inner monologue only (1–2 lines), image-rich and associative.
        """).strip()

    async def speak(self, user_text: str) -> str:
        """Produce Inland Empire inner monologue (1–2 lines), with memory support."""
        # --- HelloAgents path ---
        if self._hello and self._agent is not None:
            try:
                trace_lines: List[str] = []
                if self._mem_mgr is not None:
                    mems = self._mem_mgr.retrieve_memories(
                        query=user_text, memory_types=["working", "episodic"],
                        limit=5, min_importance=0.3
                    ) or []
                    for m in mems:
                        ts = getattr(m, "timestamp", None)
                        ts_str = ts.strftime("%H:%M") if ts else ""
                        trace_lines.append(f"[{ts_str}] {m.content}")
                trace_text = "\n".join(trace_lines[:6]) if trace_lines else ""

                ctx = self._build_user_context(user_text, trace_text)

                raw = await asyncio.to_thread(self._agent.run, ctx)
                out = sanitize_inner_monologue(raw)

                # 记忆写入
                try:
                    if self._mem_mgr is not None:
                        self._mem_mgr.add_memory(
                            content=f"PERCEPTION: {user_text}",
                            memory_type="working", importance=0.5,
                            metadata={"speaker": "player", "skill": "Inland Empire"}
                        )
                        self._mem_mgr.add_memory(
                            content=f"INLAND EMPIRE: {out}",
                            memory_type="working", importance=0.6,
                            metadata={"speaker": "Inland Empire", "skill": "Inland Empire"}
                        )
                except Exception as me:
                    print(f"ℹ️ memory add failed (non-fatal): {me}")

                return out
            except Exception as e:
                print(f"⚠️ HelloAgents speak failed, soft-fallback this call: {e}")


        # --- Fallback path (OpenAI-compatible or Echo) ---
        trace_text = self._ring.fmt() if self._ring else ""
        ctx = self._build_user_context(user_text, trace_text)
        messages = [
            {"role": "system", "content": INLAND_PERSONA},
            {"role": "user", "content": ctx},
        ]
        raw = await self._llm.acomplete(
            messages, temperature=self.temperature, max_tokens=self.max_tokens
        )
        out = sanitize_inner_monologue(raw)
        if self._ring:
            self._ring.add("Perception", user_text)
            self._ring.add("Inland Empire", out)
        return out

    async def speak_logic(self, user_text: str) -> str:
        """Produce LOGIC inner monologue (1–2 lines) about the same perception."""
        # --- HelloAgents path ---
        if self._hello and self._logic_agent is not None:
            try:
                # 这里可以简单复用 Inland 的 trace；也可以单独逻辑
                trace_text = "(shared trace with Inland Empire)"
                ctx = textwrap.dedent(f"""
                [PERCEPTION]
                {user_text}

                [INSTRUCTIONS]
                Analyze with LOGIC. Be dry and explicit about assumptions and gaps.
                """).strip()
                raw = await asyncio.to_thread(self._logic_agent.run, ctx)
                return sanitize_inner_monologue(raw)
            except Exception as e:
                print(f"⚠️ HelloAgents Logic speak failed, soft-fallback this call: {e}")
                
        # --- Fallback path ---
        trace_text = self._ring.fmt() if self._ring else ""
        # 对 LOGIC，用更偏分析的 context
        ctx = textwrap.dedent(f"""
        [PERCEPTION]
        {user_text}

        [TRACE]
        {trace_text or "(no memory)"}

        [INSTRUCTIONS]
        You are LOGIC. Analyze the situation with cold deduction.
        Point out assumptions, missing information, and the most likely explanation.
        1–2 short lines, inner monologue. No greetings, no questions.
        """).strip()
        messages = [
            {"role": "system", "content": LOGIC_PERSONA},
            {"role": "user", "content": ctx},
        ]
        raw = await self._llm.acomplete(
            messages, temperature=self.temperature, max_tokens=self.max_tokens
        )
        out = sanitize_inner_monologue(raw)
        if self._ring:
            self._ring.add("Logic-Perception", user_text)
            self._ring.add("Logic", out)
        return out

    async def speak_duo(self, user_text: str) -> Dict[str, str]:
        """
        Convenience: 同一轮里同时给出 Inland Empire + Logic。
        返回 {"primary": inland_line, "logic": logic_line}
        """
        primary = await self.speak(user_text)
        logic_line = ""
        try:
            logic_line = await self.speak_logic(user_text)
        except Exception as e:
            print(f"ℹ️ speak_logic failed (non-fatal): {e}")
        return {"primary": primary, "logic": logic_line}
    
    # -------------------- memory utils --------------------
    def get_memories(self, limit: int = 10) -> List[Dict]:
        if self._hello and self._mem_mgr is not None:
            try:
                mems = self._mem_mgr.retrieve_memories(
                    query="", memory_types=["working", "episodic"], limit=limit
                ) or []
                out: List[Dict] = []
                for m in mems:
                    out.append({
                        "content": m.content,
                        "type": getattr(m, "memory_type", "working"),
                        "importance": getattr(m, "importance", 0.5),
                        "timestamp": getattr(m, "timestamp", None).isoformat()
                        if getattr(m, "timestamp", None) else None,
                        "metadata": getattr(m, "metadata", {}),
                    })
                return out
            except Exception as e:
                print(f"ℹ️ get_memories from HelloAgents failed: {e}")

        if self._ring:
            return [
                {"t": x["t"], "role": x["role"], "text": x["text"]}
                for x in self._ring.dump()
            ][-limit:]
        return []

    def clear_memory(self):
        if self._hello and self._mem_mgr is not None:
            try:
                self._mem_mgr.clear_memory_type("working")
                self._mem_mgr.clear_memory_type("episodic")
            except Exception as e:
                print(f"ℹ️ clear_memory (HelloAgents) failed: {e}")
        if self._ring:
            self._ring.clear()
