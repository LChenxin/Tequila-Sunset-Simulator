from __future__ import annotations
import os, sys, time, re, textwrap
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import deque
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'HelloAgents'))
from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.memory import MemoryManager, MemoryConfig, MemoryItem
from openai import AsyncOpenAI

HELLO_OK = True
_OPENAI_OK = False


class FallbackLLM:
    """OpenAI-compatible async wrapper with echo fallback."""
    def __init__(self, model: str, api_key: Optional[str], base_url: str):
        self.model = model
        self.echo = not (_OPENAI_OK and api_key)
        if not self.echo:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def acomplete(self, messages, temperature=0.8, max_tokens=160) -> str:
        if self.echo:
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return f"(ECHO) {last_user[:180]}"
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=temperature, max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()

class RingMemory:
    def __init__(self, maxlen=8):
        self.buf = deque(maxlen=maxlen)
    def add(self, role: str, text: str):
        self.buf.append({"t": time.time(), "role": role, "text": text})
    def dump(self) -> List[Dict]:
        return list(self.buf)
    def fmt(self) -> str:
        if not self.buf: return "(no memory)"
        return "\n".join(f"[{x['role'].upper()}] {x['text']}" for x in self.buf)
    def clear(self):
        self.buf.clear()

# --- Style sanitization: no greetings, no questions, max 2 lines ---
GREET_RE = re.compile(r'^\s*(hi|hello|hey|greetings|bonjour|salut|你好|嗨)[,!\.\s-]*', re.I)
def sanitize_inner_monologue(text: str) -> str:
    t = (text or "").strip()
    t = GREET_RE.sub('', t).strip()
    if t.endswith('?') and '\n' not in t:
        t = t.rstrip(' ?！!。.') + '.'
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return "\n".join(lines[:2])

# --- INLAND EMPIRE persona  ---
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

# --- Public Agent (single skill) ---
@dataclass
class InlandEmpireAgent:
    model_name: str = "gpt-4o-mini"
    api_key: Optional[str] = os.getenv("API_KEY")
    base_url: str = os.getenv("BASE_URL", "https://api.openai.com/v1")
    memory_dir: Optional[str] = None
    temperature: float = 0.95
    max_tokens: int = 140

    # runtime
    _hello: bool = field(init=False, default=HELLO_OK)
    _llm: object = field(init=False, default=None)
    _agent: Optional[SimpleAgent] = field(init=False, default=None)   # HelloAgents path
    _mem_mgr: Optional[MemoryManager] = field(init=False, default=None)
    _ring: Optional[RingMemory] = field(init=False, default=None)     # Fallback path

    def __post_init__(self):
        # Prefer HelloAgents
        if self._hello:
            try:
                self._llm = HelloAgentsLLM()  # use its own env config
                self._agent = SimpleAgent(
                    name="Inland Empire",
                    llm=self._llm,
                    system_prompt=self._build_hello_system_prompt()
                )
                # Memory
                mem_dir = self.memory_dir or os.path.join(os.path.dirname(__file__), "memory_data", "InlandEmpire")
                os.makedirs(mem_dir, exist_ok=True)
                cfg = MemoryConfig(
                    storage_path=mem_dir,
                    working_memory_capacity=10,
                    working_memory_tokens=2000,
                    episodic_memory_capacity=100,
                    enable_forgetting=True,
                    forgetting_threshold=0.3
                )
                self._mem_mgr = MemoryManager(
                    config=cfg, user_id="InlandEmpire",
                    enable_working=True, enable_episodic=True,
                    enable_semantic=False, enable_perceptual=False
                )
                return
            except Exception:
                # fallthrough to internal
                self._hello = False

        # Fallback: our own minimal stack
        self._llm = FallbackLLM(self.model_name, self.api_key, self.base_url)
        self._ring = RingMemory(8)

    def _build_hello_system_prompt(self) -> str:
        # HelloAgents 的 SimpleAgent使用 system_prompt；我们在其上附加“输出契约”
        return INLAND_PERSONA + textwrap.dedent("""
        [OUTPUT CONTRACT]
        - Thought triggered by PERCEPTION.
        - 1–2 short lines, inner monologue. No greetings, no questions.
        - Do not address the player directly.
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
        if self._hello:
            # Pull some memories (optional) and build enhanced message
            trace_lines = []
            if self._mem_mgr:
                mems = self._mem_mgr.retrieve_memories(
                    query=user_text, memory_types=["working","episodic"],
                    limit=5, min_importance=0.3
                ) or []
                for m in mems:
                    ts = getattr(m, "timestamp", None)
                    ts_str = ts.strftime("%H:%M") if ts else ""
                    trace_lines.append(f"[{ts_str}] {m.content}")
            trace_text = "\n".join(trace_lines[:6]) if trace_lines else ""

            ctx = self._build_user_context(user_text, trace_text)
            out = self._agent.run(ctx)  # HelloAgents SimpleAgent is sync
            out = sanitize_inner_monologue(out)

            # Save to memory
            if self._mem_mgr:
                self._mem_mgr.add_memory(
                    content=f"PERCEPTION: {user_text}",
                    memory_type="working", importance=0.5,
                    metadata={"speaker":"player","skill":"Inland Empire"}
                )
                self._mem_mgr.add_memory(
                    content=f"INLAND EMPIRE: {out}",
                    memory_type="working", importance=0.6,
                    metadata={"speaker":"Inland Empire","skill":"Inland Empire"}
                )
            return out

        # Fallback path (async OpenAI / echo)
        trace_text = self._ring.fmt() if self._ring else ""
        ctx = self._build_user_context(user_text, trace_text)
        messages = [{"role":"system","content":INLAND_PERSONA},
                    {"role":"user","content":ctx}]
        out = await self._llm.acomplete(messages, temperature=self.temperature, max_tokens=self.max_tokens)
        out = sanitize_inner_monologue(out)
        if self._ring:
            self._ring.add("Perception", user_text)
            self._ring.add("Inland Empire", out)
        return out

    # --- memory utils ---
    def get_memories(self, limit: int = 10) -> List[Dict]:
        if self._hello and self._mem_mgr:
            mems = self._mem_mgr.retrieve_memories(query="", memory_types=["working","episodic"], limit=limit) or []
            out = []
            for m in mems:
                out.append({
                    "content": m.content,
                    "type": getattr(m, "memory_type", "working"),
                    "importance": getattr(m, "importance", 0.5),
                    "timestamp": getattr(m, "timestamp", None).isoformat() if getattr(m, "timestamp", None) else None,
                    "metadata": getattr(m, "metadata", {})
                })
            return out
        if self._ring:
            return [{"t": x["t"], "role": x["role"], "text": x["text"]} for x in self._ring.dump()][-limit:]
        return []

    def clear_memory(self):
        if self._hello and self._mem_mgr:
            try:
                self._mem_mgr.clear_memory_type("working")
                self._mem_mgr.clear_memory_type("episodic")
            except Exception:
                pass
        if self._ring:
            self._ring.clear()
