"""
CyberLibrarian – Streamlit UI.

Run with:
    streamlit run app/streamlit_app.py

Set USE_MOCK=false in .env (or the environment) to route to the real API.
Set ADMIN_MODE=true to show log-download buttons (useful on hosted deployments
where the local filesystem is wiped between restarts).
Set TEST_ROUND=round1 (or round2) to tag usage-log entries by round.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import uuid
from pathlib import Path

# Ensure repo root is on sys.path regardless of invocation directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.client import ask
from src.common.config import Config
from src.common.schemas import AnswerResponse

PROJECT_NAME = "CyberLibrarian"
USAGE_LOG    = _REPO_ROOT / "data" / "usage_log.jsonl"
ADMIN_MODE   = os.getenv("ADMIN_MODE", "false").lower() not in ("false", "0", "no")
TEST_ROUND   = os.getenv("TEST_ROUND", "")

# ---------------------------------------------------------------------------
# Page config – must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=PROJECT_NAME,
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – citation chips, card styling, dark/light compatibility
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Citation chips inside answer text */
    .cite-chip {
        display: inline-block;
        background: #0057b8;
        color: #fff;
        font-size: 0.68rem;
        font-weight: 600;
        border-radius: 4px;
        padding: 1px 5px;
        margin: 0 2px;
        cursor: pointer;
        vertical-align: middle;
        text-decoration: none;
    }
    /* Source cards */
    .source-card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .source-card.highlighted {
        border-color: #0057b8;
        background: rgba(0, 87, 184, 0.06);
    }
    /* Score badge */
    .score-badge {
        display: inline-block;
        background: rgba(128,128,128,0.15);
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    /* Meta line */
    .meta-line {
        font-size: 0.78rem;
        opacity: 0.65;
    }
    /* "I don't know" banner */
    .unknown-banner {
        background: rgba(255, 165, 0, 0.12);
        border-left: 4px solid orange;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "response" not in st.session_state:
    st.session_state.response = None
if "feedback_sent" not in st.session_state:
    st.session_state.feedback_sent = False
if "highlighted_citation" not in st.session_state:
    st.session_state.highlighted_citation = None
# Stable random id per browser session – never contains IP or name.
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _answer_with_chips(answer_text: str, n_citations: int) -> str:
    """Replace [N] markers in answer_text with styled HTML chip anchors."""
    import re
    def replace(m: re.Match) -> str:
        n = m.group(1)
        return (
            f'<a class="cite-chip" href="#source-{n}" '
            f'onclick="void(0)">[{n}]</a>'
        )
    return re.sub(r"\[(\d+)\]", replace, answer_text)


def _save_feedback(question: str, answer: str, rating: str, comment: str) -> None:
    """Append a feedback record to data/feedback.jsonl."""
    Config.FEEDBACK_JSONL.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "question": question,
        "answer": answer[:500],
        "rating": rating,
        "comment": comment,
    }
    with open(Config.FEEDBACK_JSONL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _log_usage(
    question: str,
    resp: AnswerResponse,
    rating: str | None = None,
) -> None:
    """Append one line to data/usage_log.jsonl.

    Never logs IPs or user names.  Fields:
      timestamp, session_id, round, question, answerable,
      top_source_ids, latency_ms, cost, rating (optional).
    """
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    record: dict = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": st.session_state.session_id,
        "round": TEST_ROUND,
        "question": question,
        "answerable": resp.answerable,
        "top_source_ids": [r.chunk.chunk_id for r in resp.chunks[:5]],
        "latency_ms": resp.latency_ms,
        "cost": resp.cost,
    }
    if rating is not None:
        record["rating"] = rating
    with USAGE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _source_badge(source: str) -> str:
    colors = {"owasp": "#e63946", "nist": "#1d3557", "mitre": "#457b9d", "cisa": "#2a9d8f"}
    color = colors.get(source, "#555")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 6px;'
        f'border-radius:3px;font-size:0.72rem;font-weight:600;">'
        f'{source.upper()}</span>'
    )


def _chunk_url(chunk_id: str, citations: list) -> str:
    """Look up the URL for a chunk from the citations list; return '' if absent."""
    for c in citations:
        if c.chunk_id == chunk_id:
            return c.url
    return ""


# ---------------------------------------------------------------------------
# Sidebar – filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Filters")
    selected_sources = st.multiselect(
        "Source",
        options=["owasp", "nist", "mitre", "cisa"],
        default=[],
        help="Leave empty to search all sources",
    )
    current_year = datetime.datetime.now().year
    year_range = st.slider(
        "Year range",
        min_value=2010,
        max_value=current_year,
        value=(2015, current_year),
    )

    st.divider()
    mode_label = "Mock mode" if Config.USE_MOCK else "Live mode"
    mode_color = "orange" if Config.USE_MOCK else "green"
    st.markdown(
        f'<span style="color:{mode_color};font-weight:600;">● {mode_label}</span>',
        unsafe_allow_html=True,
    )
    if Config.USE_MOCK:
        st.caption("Set USE_MOCK=false in .env to connect to the real API.")

    # ADMIN_MODE: download buttons for log files so they survive a server wipe.
    if ADMIN_MODE:
        st.divider()
        st.markdown("**Admin downloads**")
        for log_path, label in [
            (USAGE_LOG, "usage_log.jsonl"),
            (Config.FEEDBACK_JSONL, "feedback.jsonl"),
        ]:
            if log_path.exists():
                data = log_path.read_bytes()
                st.download_button(
                    label=f"Download {label}",
                    data=data,
                    file_name=label,
                    mime="application/json",
                )
            else:
                st.caption(f"{label}: no data yet")

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title(f"🔐 {PROJECT_NAME}")
st.caption("AI-powered cybersecurity knowledge assistant — OWASP · NIST · MITRE ATT&CK")

# Consent notice required for any data collection.
st.info(
    "Questions and ratings are logged anonymously for a course project. "
    "No names or IP addresses are stored."
)

question_input = st.text_area(
    "Ask a cybersecurity question",
    placeholder="e.g. How should I respond to a ransomware incident?",
    height=80,
    key="question_input",
    max_chars=500,
)

submit = st.button("Ask", type="primary", use_container_width=False)

# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------
if submit:
    st.session_state.feedback_sent = False
    st.session_state.highlighted_citation = None

    if not question_input.strip():
        st.warning("Please enter a question before submitting.")
    else:
        filters: dict = {}
        if selected_sources:
            filters["source"] = selected_sources
        if year_range != (2010, current_year):
            filters["year_min"] = year_range[0]
            filters["year_max"] = year_range[1]

        with st.spinner("Searching the corpus..."):
            try:
                response: AnswerResponse = ask(question_input.strip(), filters or None)
                st.session_state.response = response
                st.session_state.question = question_input.strip()
                # Log immediately; rating is updated on thumb press.
                _log_usage(question_input.strip(), response)
            except Exception as exc:
                st.error(
                    f"Could not reach the API. "
                    f"Make sure the server is running at **{Config.API_URL}** "
                    f"or enable mock mode with `USE_MOCK=true`.\n\n`{exc}`"
                )

# ---------------------------------------------------------------------------
# Display response
# ---------------------------------------------------------------------------
if st.session_state.response is not None:
    resp: AnswerResponse = st.session_state.response

    st.divider()

    # ---- Not-answerable banner ------------------------------------------
    if not resp.answerable:
        st.markdown(
            '<div class="unknown-banner">'
            "<strong>I don't know based on the available documents.</strong> "
            "The corpus does not appear to contain enough information to answer "
            "this question reliably."
            "</div>",
            unsafe_allow_html=True,
        )

    # ---- Answer text with citation chips --------------------------------
    answer_html = _answer_with_chips(resp.answer, len(resp.citations))
    st.markdown(answer_html, unsafe_allow_html=True)

    # ---- Meta line -------------------------------------------------------
    st.markdown(
        f'<div class="meta-line">'
        f"⏱ {resp.latency_ms} ms &nbsp;·&nbsp; "
        f"🔤 {resp.tokens} tokens &nbsp;·&nbsp; "
        f"💰 ${resp.cost:.4f}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ---- Sources panel ---------------------------------------------------
    if resp.chunks:
        with st.expander(f"Sources ({len(resp.chunks)})", expanded=False):
            for idx, result in enumerate(resp.chunks):
                chunk = result.chunk
                citation_id = idx + 1
                is_highlighted = st.session_state.highlighted_citation == citation_id
                card_class = "source-card highlighted" if is_highlighted else "source-card"

                badge     = _source_badge(chunk.source)
                score_html = f'<span class="score-badge">score {result.score:.2f}</span>'
                # URL comes from the citation list, not from Chunk (Chunk has no url field).
                url = _chunk_url(chunk.chunk_id, resp.citations)

                st.markdown(
                    f'<div class="{card_class}" id="source-{citation_id}">'
                    f'<div style="margin-bottom:4px;">'
                    f'<a class="cite-chip">[{citation_id}]</a> '
                    f"{badge} {score_html}"
                    f"</div>"
                    f"<strong>{chunk.title}</strong>"
                    + (f" — {chunk.section}" if chunk.section else "")
                    + f'<br><span class="meta-line">'
                    + (
                        f'<a href="{url}" target="_blank">'
                        f'{url[:70]}{"..." if len(url) > 70 else ""}</a>'
                        if url else "<em>no url</em>"
                    )
                    + f"</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.caption(chunk.text[:400] + ("..." if len(chunk.text) > 400 else ""))

    # ---- Feedback --------------------------------------------------------
    st.divider()
    if not st.session_state.feedback_sent:
        st.markdown("**Was this answer helpful?**")
        col_up, col_down, _ = st.columns([1, 1, 8])
        with col_up:
            thumbs_up = st.button("👍", key="thumbs_up")
        with col_down:
            thumbs_down = st.button("👎", key="thumbs_down")

        if thumbs_up or thumbs_down:
            rating = "up" if thumbs_up else "down"
            comment = st.text_input("Optional comment", key="feedback_comment")
            if st.button("Submit feedback", key="submit_feedback"):
                _save_feedback(
                    question=st.session_state.get("question", ""),
                    answer=resp.answer,
                    rating=rating,
                    comment=comment,
                )
                # Update the latest usage-log entry with the rating.
                _log_usage(
                    st.session_state.get("question", ""),
                    resp,
                    rating=rating,
                )
                st.session_state.feedback_sent = True
                st.rerun()
    else:
        st.success("Thank you for your feedback!")
