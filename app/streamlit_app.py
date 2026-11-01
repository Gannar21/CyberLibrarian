"""
CyberLibrarian – Streamlit UI (soft white & grey, multi-chat with history).

Run with:
    streamlit run app/streamlit_app.py

Set USE_MOCK=false in .env (or the environment) to route to the real API.
Set ADMIN_MODE=true to show log-download buttons (useful on hosted deployments
where the local filesystem is wiped between restarts).
Set TEST_ROUND=round1 (or round2) to tag usage-log entries by round.

Chats are saved to data/chats/<id>.json. The id lives in the page URL
(?sid=...), so history survives a browser refresh.
"""
from __future__ import annotations

import datetime
import html
import json
import os
import re
import sys
import uuid
from pathlib import Path

# Ensure repo root is on sys.path regardless of invocation directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.client import ask
from app.utils import chunk_url_from_citations, log_usage, new_session_id, save_feedback
from app.utils import USAGE_LOG
from src.common.config import Config
from src.common.schemas import AnswerResponse

PROJECT_NAME = "CyberLibrarian"
ADMIN_MODE   = os.getenv("ADMIN_MODE", "false").lower() not in ("false", "0", "no")
TEST_ROUND   = os.getenv("TEST_ROUND", "")
CHAT_DIR     = _REPO_ROOT / "data" / "chats"

EXAMPLES = [
    "How do I prevent SQL injection?",
    "How should passwords be stored securely?",
    "What is MITRE ATT&CK technique T1059?",
]

# ---------------------------------------------------------------------------
# Page config – must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=PROJECT_NAME,
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – soft white & grey, rounded, ChatGPT / Claude-ish
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    :root {
        --bg:        #ffffff;
        --bg-soft:   #f7f7f8;
        --bg-chip:   #ececf0;
        --border:    #e5e5ea;
        --text:      #2b2b30;
        --text-soft: #8a8a94;
        --accent:    #2f2f35;
    }

    /* ---------- Base ---------- */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background: var(--bg) !important;
        color: var(--text);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 7rem; }
    .stApp p, .stApp label, .stApp li, .stApp span { color: var(--text); }
    hr { border-color: var(--border) !important; }

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {
        background: var(--bg-soft) !important;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] h1 { font-size: 1.05rem; font-weight: 600; }
    .side-label {
        color: var(--text-soft) !important; font-size: 0.74rem; font-weight: 500;
        margin: 0.9rem 0 0.2rem 0.25rem;
    }
    /* chat list rows: flat, left-aligned, rounded */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"],
    [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        background: transparent;
        border: none;
        border-radius: 12px;
        padding: 0.45rem 0.7rem;
        font-weight: 400;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover,
    [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background: var(--bg-chip);
    }
    [data-testid="stSidebar"] button[data-testid="stPopoverButton"],
    [data-testid="stSidebar"] [data-testid="stPopover"] > button {
        border: none; background: transparent; padding: 0.35rem 0.4rem;
        border-radius: 10px; min-width: 0;
    }

    /* ---------- Hero ---------- */
    .hero { text-align: center; margin: 2.2rem 0 1.4rem; }
    .hero .logo {
        width: 58px; height: 58px; margin: 0 auto 0.8rem;
        border-radius: 20px; background: var(--bg-soft);
        border: 1px solid var(--border);
        display: flex; align-items: center; justify-content: center; font-size: 1.7rem;
    }
    .hero h1 { font-size: 1.7rem; font-weight: 600; letter-spacing: -0.02em; margin: 0; padding: 0; }
    .hero p { color: var(--text-soft) !important; margin: 0.35rem 0 0; font-size: 0.95rem; }

    /* ---------- Inputs ---------- */
    .stTextInput input {
        background: var(--bg-soft) !important; color: var(--text) !important;
        border: 1px solid var(--border) !important; border-radius: 14px !important;
        padding: 0.55rem 0.9rem !important;
    }
    .stTextInput > div > div { border: none !important; box-shadow: none !important; background: transparent !important; }
    [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: var(--bg) !important; }
    [data-testid="stChatInput"] > div {
        background: var(--bg-soft) !important;
        border: 1px solid var(--border) !important;
        border-radius: 26px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    [data-testid="stChatInput"] textarea { color: var(--text) !important; }

    /* ---------- Buttons ---------- */
    .stButton > button, .stDownloadButton > button {
        border-radius: 999px; border: 1px solid var(--border);
        background: #fff; color: var(--text); font-weight: 500;
        padding: 0.4rem 1.1rem; transition: background .15s, transform .1s;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: var(--bg-soft); border-color: #d4d4db; color: var(--text);
    }
    .stButton > button:active { transform: scale(0.97); }
    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: var(--accent) !important; color: #fff !important;
        border-color: var(--accent) !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover { background: #000 !important; }
    .stButton > button[kind="primary"] p,
    button[data-testid="stBaseButton-primary"] p { color: #fff !important; }

    /* ---------- Chat ---------- */
    [data-testid="stChatMessage"] { background: transparent !important; padding: 0.4rem 0; }
    [data-testid="stChatMessageAvatarAssistant"] {
        background: var(--bg-soft) !important; border: 1px solid var(--border);
    }
    .user-row { display: flex; justify-content: flex-end; margin: 1.1rem 0 0.9rem; }
    .user-bubble {
        background: var(--bg-chip); border-radius: 20px 20px 6px 20px;
        padding: 0.65rem 1.05rem; max-width: 82%; font-size: 0.95rem;
    }
    .cite-chip {
        display: inline-block; background: var(--bg-chip); color: #55555e !important;
        font-size: 0.68rem; font-weight: 600; border-radius: 999px;
        padding: 1px 7px; margin: 0 2px; vertical-align: middle; text-decoration: none !important;
    }
    .cite-chip:hover { background: #dcdce2; }
    .meta-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 0.6rem 0 0.2rem; }
    .meta-pill {
        background: var(--bg-soft); border: 1px solid var(--border); color: var(--text-soft);
        font-size: 0.74rem; border-radius: 999px; padding: 2px 10px;
    }
    .meta-line { font-size: 0.78rem; color: var(--text-soft); }
    .meta-line a { color: var(--text-soft) !important; text-decoration: underline; }
    .unknown-banner {
        background: var(--bg-soft); border: 1px solid var(--border);
        border-radius: 16px; padding: 0.8rem 1.1rem; font-size: 0.92rem;
    }

    /* ---------- Sources ---------- */
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important; border-radius: 16px !important;
        background: #fff; overflow: hidden;
    }
    [data-testid="stExpander"] summary { font-size: 0.9rem; color: var(--text-soft); }
    .source-card {
        border: 1px solid var(--border); border-radius: 14px;
        padding: 0.75rem 1rem; margin: 0.6rem 0 0.2rem; background: var(--bg-soft);
    }
    .score-badge {
        display: inline-block; background: #fff; border: 1px solid var(--border);
        border-radius: 999px; padding: 0 8px; font-size: 0.72rem; color: var(--text-soft);
    }
    [data-testid="stCaptionContainer"] { color: var(--text-soft) !important; }
    .stAlert { border-radius: 14px; }
    .mode-dot { font-size: 0.8rem; font-weight: 500; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Chat storage (JSON file per browser id, id kept in the URL)
# ---------------------------------------------------------------------------

def _valid_uid(value: str | None) -> bool:
    return bool(value) and re.fullmatch(r"[A-Za-z0-9]{8,64}", value) is not None


def _empty_store() -> dict:
    return {"chats": {}, "order": [], "active": None}


def _load_store(uid: str) -> dict:
    try:
        data = json.loads((CHAT_DIR / f"{uid}.json").read_text(encoding="utf-8"))
        if isinstance(data, dict) and {"chats", "order", "active"} <= data.keys():
            return data
    except (OSError, ValueError):
        pass
    return _empty_store()


def _save_store() -> None:
    try:
        CHAT_DIR.mkdir(parents=True, exist_ok=True)
        path = CHAT_DIR / f"{st.session_state.uid}.json"
        path.write_text(
            json.dumps(st.session_state.store, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # saving must never break the UI


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "uid" not in st.session_state:
    uid = st.query_params.get("sid")
    if not _valid_uid(uid):
        uid = uuid.uuid4().hex
        st.query_params["sid"] = uid
    st.session_state.uid = uid
    st.session_state.store = _load_store(uid)
# Stable random id per browser session for usage logs – never contains IP or name.
if "session_id" not in st.session_state:
    st.session_state.session_id = new_session_id()


# ---------------------------------------------------------------------------
# Chat CRUD
# ---------------------------------------------------------------------------

def _store() -> dict:
    return st.session_state.store


def _new_chat() -> None:
    s = _store()
    # Don't pile up empty chats: reuse the current one if it's still empty.
    cur = s["chats"].get(s["active"])
    if cur is not None and not cur["messages"]:
        return
    cid = uuid.uuid4().hex[:12]
    s["chats"][cid] = {
        "id": cid,
        "title": "New chat",
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }
    s["order"].insert(0, cid)
    s["active"] = cid
    _save_store()


def _select_chat(cid: str) -> None:
    if cid in _store()["chats"]:
        _store()["active"] = cid
        _save_store()


def _rename_chat(cid: str, widget_key: str) -> None:
    title = (st.session_state.get(widget_key) or "").strip()[:60] or "New chat"
    if cid in _store()["chats"]:
        _store()["chats"][cid]["title"] = title
        _save_store()


def _delete_chat(cid: str) -> None:
    s = _store()
    s["chats"].pop(cid, None)
    if cid in s["order"]:
        s["order"].remove(cid)
    if s["active"] == cid:
        s["active"] = s["order"][0] if s["order"] else None
    _save_store()


def _rate(cid: str, idx: int, rating: str) -> None:
    msg = _store()["chats"][cid]["messages"][idx]
    msg["rating"] = rating
    try:
        resp = AnswerResponse.model_validate(msg["response"])
        save_feedback(
            question=msg.get("question", ""),
            answer=resp.answer,
            rating=rating,
            comment="",
        )
        log_usage(st.session_state.session_id, msg.get("question", ""), resp, rating=rating)
    except Exception:
        pass
    _save_store()


def _use_example(text: str) -> None:
    st.session_state.pending_prompt = text


# Make sure there is always an active chat.
if _store()["active"] not in _store()["chats"]:
    _store()["active"] = _store()["order"][0] if _store()["order"] else None
if _store()["active"] is None:
    _new_chat()


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _answer_with_chips(answer_text: str) -> str:
    """Replace [N] markers in answer_text with styled HTML chip anchors."""
    return re.sub(
        r"\[(\d+)\]",
        lambda m: f'<a class="cite-chip" href="#source-{m.group(1)}">{m.group(1)}</a>',
        answer_text,
    )


def _source_badge(source: str) -> str:
    colors = {
        "owasp": ("#fde8ea", "#b4414d"),
        "nist":  ("#e6ebf5", "#3b4a73"),
        "mitre": ("#e5f0f6", "#3a6a85"),
        "cisa":  ("#e3f3ef", "#2f7a6c"),
    }
    bg, fg = colors.get(source, ("#ececf0", "#55555e"))
    return (
        f'<span style="background:{bg};color:{fg};padding:1px 9px;'
        f'border-radius:999px;font-size:0.72rem;font-weight:600;">{source.upper()}</span>'
    )


_chunk_url = chunk_url_from_citations  # alias for backward compat


def _user_bubble(text: str) -> None:
    st.markdown(
        f'<div class="user-row"><div class="user-bubble">{html.escape(text)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_response(resp: AnswerResponse) -> None:
    if not resp.answerable:
        st.markdown(
            '<div class="unknown-banner">'
            "<strong>Hmm, I don't know based on the available documents 🤔</strong><br>"
            "The corpus doesn't seem to have enough information to answer this reliably."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(_answer_with_chips(resp.answer), unsafe_allow_html=True)

    if resp.tokens or resp.latency_ms > 50:
        st.markdown(
            f'<div class="meta-row">'
            f'<span class="meta-pill">⏱ {resp.latency_ms} ms</span>'
            f'<span class="meta-pill">🔤 {resp.tokens} tokens</span>'
            f'<span class="meta-pill">💰 ${resp.cost:.4f}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

    if resp.chunks:
        label = "📚 Sources" if resp.answerable else "📚 Closest documents I checked"
        with st.expander(f"{label} ({len(resp.chunks)})", expanded=False):
            for idx, result in enumerate(resp.chunks):
                chunk = result.chunk
                url = _chunk_url(chunk.chunk_id, resp.citations)
                st.markdown(
                    f'<div class="source-card" id="source-{idx + 1}">'
                    f'<div style="margin-bottom:6px;">'
                    f'<a class="cite-chip">{idx + 1}</a> '
                    f'{_source_badge(chunk.source)} '
                    f'<span class="score-badge">score {result.score:.2f}</span></div>'
                    f"<strong>{chunk.title}</strong>"
                    + (f" — {chunk.section}" if chunk.section else "")
                    + '<br><span class="meta-line">'
                    + (
                        f'<a href="{url}" target="_blank">'
                        f'{url[:70]}{"..." if len(url) > 70 else ""}</a>'
                        if url else "<em>no url</em>"
                    )
                    + "</span></div>",
                    unsafe_allow_html=True,
                )
                st.caption(chunk.text[:400] + ("..." if len(chunk.text) > 400 else ""))


def _render_message(cid: str, idx: int, msg: dict) -> None:
    if msg["role"] == "user":
        _user_bubble(msg["content"])
        return

    with st.chat_message("assistant", avatar="🔐"):
        try:
            resp = AnswerResponse.model_validate(msg["response"])
        except Exception:
            st.markdown(msg.get("content", ""))
            return
        _render_response(resp)

        rating = msg.get("rating")
        if rating:
            st.caption("Thanks for the feedback 💙" + ("  👍" if rating == "up" else "  👎"))
        else:
            c1, c2, _ = st.columns([1, 1, 8])
            c1.button("👍", key=f"up_{cid}_{idx}", on_click=_rate, args=(cid, idx, "up"))
            c2.button("👎", key=f"down_{cid}_{idx}", on_click=_rate, args=(cid, idx, "down"))


# ---------------------------------------------------------------------------
# Sidebar – new chat, history, filters
# ---------------------------------------------------------------------------
current_year = datetime.datetime.now().year

with st.sidebar:
    st.title("🔐 CyberLibrarian")
    st.button("＋  New chat", type="primary", use_container_width=True, on_click=_new_chat)

    st.markdown('<div class="side-label">Your chats</div>', unsafe_allow_html=True)
    s = _store()
    for cid in list(s["order"]):
        chat = s["chats"][cid]
        title = chat["title"]
        label = title if len(title) <= 28 else title[:27] + "…"
        if cid == s["active"]:
            label = "● " + label
        row, menu = st.columns([6, 1], vertical_alignment="center")
        row.button(
            label, key=f"chat_{cid}", use_container_width=True,
            on_click=_select_chat, args=(cid,),
        )
        with menu.popover("⋯"):
            rn_key = f"rn_{cid}"
            st.text_input(
                "Rename chat", value=title, key=rn_key, max_chars=60,
            )
            st.button("Save name", key=f"rs_{cid}", on_click=_rename_chat, args=(cid, rn_key))
            st.button("🗑 Delete chat", key=f"del_{cid}", on_click=_delete_chat, args=(cid,))

    st.divider()
    with st.expander("Filters", expanded=False):
        selected_sources = st.multiselect(
            "Source",
            options=["owasp", "nist", "mitre", "cisa"],
            default=[],
            help="Leave empty to search all sources",
        )
        year_range = st.slider(
            "Year range",
            min_value=2010,
            max_value=current_year,
            value=(2015, current_year),
        )

    mode_label = "Mock mode" if Config.USE_MOCK else "Live mode"
    mode_color = "#e0a030" if Config.USE_MOCK else "#3aa76d"
    st.markdown(
        f'<span class="mode-dot" style="color:{mode_color};">● {mode_label}</span>',
        unsafe_allow_html=True,
    )
    if Config.USE_MOCK:
        st.caption("Set USE_MOCK=false in .env to connect to the real API.")
    st.caption(
        "Questions and ratings are logged anonymously for a course project. "
        "No names or IP addresses are stored. Chats are saved on this server "
        "so your history stays after a refresh."
    )

    # ADMIN_MODE: download buttons for log files so they survive a server wipe.
    if ADMIN_MODE:
        st.divider()
        st.markdown("**Admin downloads**")
        for log_path, label in [
            (USAGE_LOG, "usage_log.jsonl"),
            (Config.FEEDBACK_JSONL, "feedback.jsonl"),
        ]:
            if log_path.exists():
                st.download_button(
                    label=f"Download {label}",
                    data=log_path.read_bytes(),
                    file_name=label,
                    mime="application/json",
                )
            else:
                st.caption(f"{label}: no data yet")

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
active_id = _store()["active"]
chat = _store()["chats"][active_id]

prompt = st.chat_input("Ask a cybersecurity question…", max_chars=500)
if not prompt:
    prompt = st.session_state.pop("pending_prompt", None)
prompt = prompt.strip() if prompt else None

if not chat["messages"] and not prompt:
    st.markdown(
        f"""
        <div class="hero">
            <div class="logo">🔐</div>
            <h1>{PROJECT_NAME}</h1>
            <p>Your cybersecurity helper. Ask me anything about OWASP, NIST or MITRE ATT&amp;CK ✨</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(len(EXAMPLES))
    for col, text in zip(cols, EXAMPLES):
        col.button(text, key=f"ex_{text}", use_container_width=True,
                   on_click=_use_example, args=(text,))
else:
    for i, m in enumerate(chat["messages"]):
        _render_message(active_id, i, m)

# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------
if prompt:
    filters: dict = {}
    if selected_sources:
        filters["source"] = selected_sources
    if year_range != (2010, current_year):
        filters["year_min"] = year_range[0]
        filters["year_max"] = year_range[1]

    _user_bubble(prompt)
    resp: AnswerResponse | None = None
    with st.chat_message("assistant", avatar="🔐"):
        with st.spinner("Searching the corpus..."):
            try:
                resp = ask(prompt, filters or None)
            except Exception as exc:
                st.error(
                    f"Could not reach the API. "
                    f"Make sure the server is running at **{Config.API_URL}** "
                    f"or enable mock mode with `USE_MOCK=true`.\n\n`{exc}`"
                )

    if resp is not None:
        if not chat["messages"]:
            chat["title"] = prompt[:40] + ("…" if len(prompt) > 40 else "")
        chat["messages"].append({"role": "user", "content": prompt})
        chat["messages"].append({
            "role": "assistant",
            "content": resp.answer,
            "question": prompt,
            "response": resp.model_dump(mode="json"),
            "rating": None,
        })
        # Log immediately; the rating is added when a thumb is pressed.
        log_usage(st.session_state.session_id, prompt, resp)
        _save_store()
        st.rerun()