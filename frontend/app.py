import os
import time
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
SESSION_KEY = "tss_session_id"
DEFAULT_SESSION = "demo-ui-001"

st.set_page_config(page_title="Tequila Sunset Simulator (PoC)", layout="centered")

# --- Sidebar ---
st.sidebar.title("Tequila Sunset Simulator")
api_base = st.sidebar.text_input("API Base", value=API_BASE)
session_id = st.sidebar.text_input("Session ID", value=st.session_state.get(SESSION_KEY, DEFAULT_SESSION))
col_a, col_b = st.sidebar.columns(2)

if col_a.button("Reset Session", use_container_width=True):
    try:
        r = requests.post(f"{api_base}/v1/reset", json={"session_id": session_id}, timeout=15)
        st.sidebar.success(r.json())
    except Exception as e:
        st.sidebar.error(f"Reset failed: {e}")
    st.session_state[SESSION_KEY] = session_id

if col_b.button("Refresh State", use_container_width=True):
    pass  # just fall through to refresh block below

# --- Main ---
st.title("Inland Empire — Inner Monologue (PoC)")
user_text = st.text_area(
    "Perception (what the character perceives):",
    placeholder="The neon blinks twice, like a tired eye.",
    height=120,
)

send = st.button("Speak", type="primary")

if send and user_text.strip():
    try:
        payload = {"user_text": user_text.strip(), "session_id": session_id}
        r = requests.post(f"{api_base}/v1/step", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        st.session_state["last_rendered"] = data.get("rendered", "")
        st.session_state["last_primary"] = data.get("primary", "")
        st.session_state["last_chorus"] = data.get("chorus", [])
        st.session_state[SESSION_KEY] = data.get("session_id", session_id)
    except Exception as e:
        st.error(f"Call failed: {e}")

# Show latest response
if "last_rendered" in st.session_state:
    st.subheader("Rendered")
    st.code(st.session_state["last_rendered"])

if "last_chorus" in st.session_state and st.session_state["last_chorus"]:
    st.subheader("Chorus (other skills)")
    for line in st.session_state["last_chorus"]:
        st.markdown(f"- {line}")

# Live state on the right column
st.divider()
st.subheader("Session State")

try:
    resp = requests.get(f"{api_base}/v1/state", params={"session_id": session_id}, timeout=15)
    state = resp.json()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Turn", state.get("turn", 0))
    with c2:
        st.write("Mood (PoC):", state.get("mood", {}))
    st.caption("Shared Trace (latest)")
    st.json(state.get("shared_trace", []))
    st.caption("Agents (PoC: mirrored)")
    st.json(state.get("agents", {}))
except Exception as e:
    st.warning(f"Cannot fetch /v1/state: {e}")

st.caption("Tip: set API_BASE env var to point at a remote server if needed.")
