"""CyberLibrarian chat UI. Run from the project root: streamlit run app/streamlit_app.py"""
from __future__ import annotations

import html
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
import streamlit as st

from src.common.config import Config

CHATS_FILE = ROOT / "data" / "chats.json"
SOURCE_LABELS = {"owasp": "OWASP", "nist": "NIST", "mitre": "MITRE ATT&CK", "cisa": "CISA"}
EXAMPLES = [
    "What is SQL injection and how do I prevent it?",
    "What are the phases of incident response in NIST SP 800-61?",
    "How should passwords be stored securely?",
    "What is the MITRE ATT&CK technique T1059?",
]

st.set_page_config(page_title="CyberLibrarian", layout="wide")

st.markdown(
    """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {max-width: 780px; padding-top: 2.5rem; padding-bottom: 6rem;}

/* Sidebar: flat ChatGPT-like list */
section[data-testid="stSidebar"] .stButton > button {
    border: none; background: transparent; box-shadow: none;
    justify-content: flex-start; text-align: left; font-weight: 400;
    padding: .45rem .7rem; border-radius: 8px;
}
section[data-testid="stSidebar"] .stButton > button:hover {background: rgba(128,128,128,.15);}
[class*="st-key-chatactive_"] button {background: rgba(128,128,128,.22) !important;}
.st-key-new_chat button {
    border: 1px solid rgba(128,128,128,.35) !important; font-weight: 500 !important;
}
section[data-testid="stSidebar"] [data-testid="stPopover"] button {
    border: none; background: transparent; box-shadow: none; padding: .35rem .5rem;
}
section[data-testid="stSidebar"] [data-testid="stPopover"] button:hover {
    background: rgba(128,128,128,.15);
}

/* Messages: no avatars, user text in a soft bubble */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {display: none;}
[data-testid="stChatMessage"] {background: transparent; padding: .5rem 0;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: rgba(128,128,128,.13); border-radius: 16px; padding: .75rem 1.1rem;
}

/* Sources */
.src {border-left: 3px solid rgba(128,128,128,.4); padding: 2px 0 2px 12px; margin: 10px 0;}
.src .t {font-weight: 600;}
.src .m {opacity: .65; font-size: .82rem;}
.src details {margin-top: 4px;}
.src summary {cursor: pointer; opacity: .8; font-size: .85rem;}
.src .p {font-size: .85rem; opacity: .85; margin-top: 4px; white-space: pre-wrap;}
.empty-title {text-align: center; font-size: 1.9rem; font-weight: 600; margin: 4rem 0 .4rem;}
.empty-sub {text-align: center; opacity: .65; margin-bottom: 2rem;}
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Storage (chats are saved to data/chats.json so they survive restarts)
# --------------------------------------------------------------------------
def load_chats() -> dict:
    if CHATS_FILE.exists():
        try:
            return json.loads(CHATS_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_chats() -> None:
    CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHATS_FILE.write_text(
        json.dumps(st.session_state.chats, ensure_ascii=False, indent=2), "utf-8"
    )


# --------------------------------------------------------------------------
# Chat CRUD
# --------------------------------------------------------------------------
def new_chat() -> None:
    # Reuse an existing empty chat instead of piling up blank ones
    for c in st.session_state.chats.values():
        if not c["messages"]:
            st.session_state.active = c["id"]
            return
    cid = uuid.uuid4().hex[:8]
    st.session_state.chats[cid] = {
        "id": cid,
        "title": "New chat",
        "created": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }
    st.session_state.active = cid
    save_chats()


def select_chat(cid: str) -> None:
    st.session_state.active = cid


def delete_chat(cid: str) -> None:
    st.session_state.chats.pop(cid, None)
    if st.session_state.active == cid:
        st.session_state.active = None
    save_chats()


def rename_chat(cid: str) -> None:
    title = st.session_state.get(f"rename_{cid}", "").strip()
    if title and cid in st.session_state.chats:
        st.session_state.chats[cid]["title"] = title[:60]
        save_chats()


def set_pending(question: str) -> None:
    st.session_state.pending = question


def set_feedback(cid: str, idx: int, value: str) -> None:
    messages = st.session_state.chats[cid]["messages"]
    messages[idx]["feedback"] = value
    save_chats()
    try:
        Config.FEEDBACK_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with open(Config.FEEDBACK_JSONL, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "question": messages[idx - 1]["content"] if idx > 0 else "",
                        "answer": messages[idx]["content"][:500],
                        "feedback": value,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass


# --------------------------------------------------------------------------
# Backend call
# --------------------------------------------------------------------------
def ask_backend(question: str, history: list[dict]) -> dict:
    if Config.USE_MOCK:
        return {
            "answer": "This is a mock answer. Set USE_MOCK=false in .env to use the real API [1].",
            "citations": [
                {"id": 1, "chunk_id": "mock-1", "title": "Mock document", "source": "owasp",
                 "section": "Example", "url": "https://owasp.org"}
            ],
            "chunks": [{"chunk": {"chunk_id": "mock-1", "text": "Mock passage text."}, "score": 1.0}],
            "latency_ms": 5, "tokens": 0, "cost": 0.0, "answerable": True,
        }
    r = requests.post(
        f"{Config.API_URL.rstrip('/')}/ask",
        json={"question": question, "history": history},
        timeout=120,
    )
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise RuntimeError(f"HTTP {r.status_code}: {detail}")
    return r.json()


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------
def render_sources(meta: dict) -> None:
    cites = meta.get("citations") or []
    if not cites:
        if meta.get("answerable") is False:
            st.caption("No relevant passage was found in the OWASP, NIST or MITRE documents.")
        return
    chunk_by_id = {r["chunk"]["chunk_id"]: r["chunk"] for r in (meta.get("chunks") or [])}
    with st.expander(f"Sources ({len(cites)})"):
        for c in cites:
            label = SOURCE_LABELS.get(c["source"], c["source"])
            info = [html.escape(label)]
            if c.get("section"):
                info.append(html.escape(c["section"]))
            if c.get("url"):
                info.append(f'<a href="{html.escape(c["url"])}" target="_blank">Open</a>')
            passage = ""
            chunk = chunk_by_id.get(c["chunk_id"])
            if chunk:
                text = html.escape(chunk["text"][:700]) + ("..." if len(chunk["text"]) > 700 else "")
                passage = f'<details><summary>Show passage</summary><div class="p">{text}</div></details>'
            st.markdown(
                f'<div class="src"><div class="t">[{c["id"]}] {html.escape(c["title"])}</div>'
                f'<div class="m">{" &middot; ".join(info)}</div>{passage}</div>',
                unsafe_allow_html=True,
            )


def render_feedback(cid: str, idx: int, msg: dict) -> None:
    key = f"fb_{cid}_{idx}"
    if hasattr(st, "feedback"):
        def cb() -> None:
            v = st.session_state.get(key)
            if v is not None:
                set_feedback(cid, idx, "up" if v == 1 else "down")
        st.feedback("thumbs", key=key, on_change=cb)
    else:
        c1, c2, _ = st.columns([1, 1.4, 8])
        c1.button("Good", key=f"up_{cid}_{idx}", on_click=set_feedback, args=(cid, idx, "up"))
        c2.button("Not good", key=f"dn_{cid}_{idx}", on_click=set_feedback, args=(cid, idx, "down"))


def render_message(cid: str, idx: int, msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] != "assistant":
            return
        meta = msg.get("meta") or {}
        render_sources(meta)
        if meta.get("latency_ms"):
            st.caption(
                f"{meta['latency_ms'] / 1000:.1f}s  |  {meta.get('tokens', 0)} tokens  |  "
                f"${meta.get('cost', 0.0):.5f}"
            )
        if meta:
            render_feedback(cid, idx, msg)


# --------------------------------------------------------------------------
# State init
# --------------------------------------------------------------------------
if "chats" not in st.session_state:
    st.session_state.chats = load_chats()
    st.session_state.active = None
    st.session_state.pending = None

if not st.session_state.chats:
    new_chat()
if st.session_state.active not in st.session_state.chats:
    latest = max(st.session_state.chats.values(), key=lambda c: c["created"])
    st.session_state.active = latest["id"]

# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### CyberLibrarian")
    st.button("New chat", key="new_chat", use_container_width=True, on_click=new_chat)
    st.markdown("")
    st.caption("Chats")
    for chat in sorted(st.session_state.chats.values(), key=lambda c: c["created"], reverse=True):
        is_active = chat["id"] == st.session_state.active
        c1, c2 = st.columns([6, 1], vertical_alignment="center")
        c1.button(
            chat["title"][:28],
            key=("chatactive_" if is_active else "chat_") + chat["id"],
            on_click=select_chat,
            args=(chat["id"],),
            use_container_width=True,
        )
        with c2.popover("\u22ef"):
            st.text_input("Rename", value=chat["title"], key=f"rename_{chat['id']}",
                          on_change=rename_chat, args=(chat["id"],),
                          label_visibility="collapsed")
            st.caption("Press Enter to save the new name")
            st.button("Delete chat", key=f"del_{chat['id']}", on_click=delete_chat,
                      args=(chat["id"],), use_container_width=True)
    st.divider()
    st.caption("Mode: " + ("mock" if Config.USE_MOCK else f"live ({Config.API_URL})"))

# --------------------------------------------------------------------------
# Main chat area
# --------------------------------------------------------------------------
cid = st.session_state.active
if cid not in st.session_state.chats:
    st.rerun()
chat = st.session_state.chats[cid]

prompt = st.chat_input("Ask a cybersecurity question, or just say hi")
if not prompt and st.session_state.pending:
    prompt, st.session_state.pending = st.session_state.pending, None

to_answer = False
if prompt:
    chat["messages"].append({"role": "user", "content": prompt})
    if chat["title"] == "New chat":
        chat["title"] = prompt[:40]
    save_chats()
    to_answer = True

if not chat["messages"]:
    st.markdown('<div class="empty-title">What can I help you with?</div>'
                '<div class="empty-sub">Ask about OWASP, NIST or MITRE ATT&amp;CK. '
                'I find the sources and cite them.</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, q in enumerate(EXAMPLES):
        cols[i % 2].button(q, key=f"ex_{i}", on_click=set_pending, args=(q,),
                           use_container_width=True)

for i, msg in enumerate(chat["messages"]):
    render_message(cid, i, msg)

if to_answer:
    history = [{"role": m["role"], "content": m["content"]} for m in chat["messages"][:-1]][-6:]
    with st.chat_message("assistant"):
        with st.spinner("Searching the documents"):
            try:
                data = ask_backend(prompt, history)
                cited = {c["chunk_id"] for c in data.get("citations", [])}
                reply = {
                    "role": "assistant",
                    "content": data["answer"],
                    "meta": {
                        "citations": data.get("citations", []),
                        "chunks": [r for r in data.get("chunks", [])
                                   if r["chunk"]["chunk_id"] in cited],
                        "latency_ms": data.get("latency_ms"),
                        "tokens": data.get("tokens", 0),
                        "cost": data.get("cost", 0.0),
                        "answerable": data.get("answerable", True),
                    },
                }
            except requests.ConnectionError:
                reply = {"role": "assistant", "meta": {},
                         "content": f"Cannot reach the backend at {Config.API_URL}. "
                                    "Start it with: uvicorn src.api.main:app --reload"}
            except Exception as e:
                reply = {"role": "assistant", "meta": {},
                         "content": f"The backend returned an error.\n\n`{e}`"}
    chat["messages"].append(reply)
    save_chats()
    st.rerun()