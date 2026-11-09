
import os
import time
import base64
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageOps

import requests
import streamlit as st


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

API_BASE = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000",
).rstrip("/")


POLL_INTERVAL = 2
MAX_POLL_ATTEMPTS = 450

# Use the official white-on-transparent gOGig mark as the browser favicon.
FAVICON_PATH = Path(__file__).with_name("gogig_logo_dark.png")

st.set_page_config(
    page_title="gOGig Lens | Intelligent Media",
    page_icon=str(FAVICON_PATH) if FAVICON_PATH.exists() else "🟠",
    layout="wide",
)



# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --bg: #090d12;
        --surface: #101720;
        --surface-raised: #151f2b;
        --border: rgba(174, 190, 208, .13);
        --text: #f4f7fb;
        --muted: #91a0b1;
        --orange: #ff7900;
        --green: #28b56d;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 50% -18%, rgba(255,121,0,.10), transparent 42%),
            linear-gradient(180deg, #0b1118 0%, #090d12 52%, #0b1016 100%);
        color: var(--text);
    }

    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }

    .block-container {
        max-width: 1240px;
        padding: 1.15rem 2.4rem 2.4rem;
    }

    h1, h2, h3, h4 {
        color: var(--text) !important;
        letter-spacing: -.035em;
    }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.02rem !important; }
    h4 { font-size: .9rem !important; }

    p, label, li, [data-testid="stMarkdownContainer"] {
        font-size: .86rem;
    }

    .topline {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        color: var(--muted);
        font-size: .7rem;
        letter-spacing: .12em;
        text-transform: uppercase;
        padding: 0 2px 13px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 22px;
    }
    .topline strong {
        color: #dce4ed;
        font-weight: 650;
    }
    .topline .live {
        color: #79d9a5;
        letter-spacing: .08em;
    }

    .brand-hero {
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        width: 100%;
        padding: 17px 12px 25px;
        margin: 0 auto 34px;
        border: 0;
        border-radius: 0;
        background:
            radial-gradient(ellipse at 50% 0%, rgba(255,121,0,.12), transparent 55%);
        box-shadow: none;
        box-sizing: border-box;
    }
    .brand-hero:after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 30%;
        width: 40%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,121,0,.55), transparent);
    }
    .brand-logo {
        display: block;
        width: 132px;
        max-width: 42vw;
        height: auto;
        object-fit: contain;
        margin: 0 auto 4px;
        filter: drop-shadow(0 7px 15px rgba(0,0,0,.25));
    }
    .brand-product {
        width: 100%;
        margin: 0 auto;
        color: #fff;
        text-align: center;
        font-size: clamp(3rem, 7vw, 4.25rem);
        font-weight: 850;
        line-height: .94;
        letter-spacing: .11em;
        text-indent: .11em;
        text-transform: uppercase;
        text-shadow: 0 8px 28px rgba(0,0,0,.3);
    }
    .brand-product span { color: var(--orange); }
    .brand-subtitle {
        margin-top: 12px;
        color: #aab7c6;
        text-align: center;
        font-size: .72rem;
        font-weight: 600;
        letter-spacing: .16em;
        text-transform: uppercase;
    }
    .brand-chip {
        margin-top: 14px;
        display: inline-block;
        border: 1px solid rgba(255,121,0,.28);
        border-radius: 99px;
        padding: 5px 11px;
        color: #ffb16f;
        background: rgba(255,121,0,.07);
        font-size: .64rem;
        font-weight: 650;
        letter-spacing: .08em;
        text-transform: uppercase;
    }

    .eyebrow {
        color: #ffab65;
        font-size: .68rem;
        font-weight: 750;
        letter-spacing: .13em;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .section-title {
        color: #f4f7fb;
        font-size: 1.12rem;
        font-weight: 750;
        letter-spacing: -.025em;
        margin: 0 0 4px;
    }
    .section-copy {
        color: var(--muted);
        font-size: .78rem;
        line-height: 1.5;
    }

    /* Open canvas: no enclosing dashboard cards or bordered sections. */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 0 !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    div[data-testid="stFileUploader"] {
        border: 1px dashed rgba(159,177,198,.32);
        border-radius: 11px;
        padding: 9px;
        background: rgba(7,12,18,.42);
    }
    div[data-testid="stFileUploader"] label,
    div[data-testid="stFileUploader"] small,
    div[data-testid="stFileUploader"] button {
        font-size: .76rem !important;
    }
    [data-testid="stImage"] img { border-radius: 10px; }

    div.stButton > button {
        border-radius: 9px;
        min-height: 2.55rem;
        font-size: .82rem;
        font-weight: 700;
        border: 1px solid rgba(255,255,255,.12);
        transition: all .18s ease;
    }
    .stButton > button[kind="primary"] {
        color: #fff;
        background: linear-gradient(135deg, #ff861f, #ed6900);
        border: 1px solid rgba(255,171,104,.35);
        box-shadow: 0 7px 20px rgba(255,121,0,.18);
    }
    .stButton > button[kind="primary"]:hover {
        color: #fff;
        background: linear-gradient(135deg, #ff963d, #ff7900);
        border-color: rgba(255,190,140,.55);
        box-shadow: 0 9px 24px rgba(255,121,0,.24);
    }

    [data-testid="stMetric"] {
        background: transparent;
        border: 0;
        border-left: 1px solid rgba(174,190,208,.16);
        border-radius: 0;
        padding: 5px 14px;
    }
    [data-testid="column"]:first-child [data-testid="stMetric"] {
        border-left: 0;
        padding-left: 0;
    }
    [data-testid="stMetricLabel"] {
        color: #9eacbc !important;
        font-size: .72rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #f5f8fc !important;
        font-size: 1.5rem !important;
        font-weight: 750;
    }
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--muted);
        font-size: .74rem;
    }
    [data-testid="stExpander"] {
        background: rgba(16,23,32,.8);
        border: 1px solid var(--border);
        border-radius: 11px;
    }
    [data-testid="stExpander"] {
        background: linear-gradient(145deg, rgba(20,29,40,.96), rgba(13,20,29,.98)) !important;
        border: 1px solid rgba(255,121,0,.30) !important;
        border-radius: 11px !important;
    }

    [data-testid="stExpander"] summary {
        color: #ffffff !important;
        font-size: .84rem !important;
        font-weight: 750 !important;
    }

    /* Make every item inside More details readable on the dark surface. */
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"],
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stExpander"] [data-testid="stCaptionContainer"],
    [data-testid="stExpander"] .stCaption {
        color: #e6edf5 !important;
        font-size: .79rem !important;
        line-height: 1.55 !important;
    }

    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] strong {
        color: #ff9a42 !important;
        font-weight: 750 !important;
    }

    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h3,
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h4 {
        color: #ff9a42 !important;
    }

    [data-testid="stExpander"] hr {
        background: linear-gradient(90deg, rgba(255,121,0,.04), rgba(255,121,0,.48), rgba(255,121,0,.04)) !important;
    }

    .summary-trigger button {
        border: 1px solid rgba(255,121,0,.48) !important;
        color: #ffad65 !important;
        background: rgba(255,121,0,.075) !important;
        border-radius: 999px !important;
        font-weight: 750 !important;
    }

    .summary-trigger button:hover {
        border-color: #ff7900 !important;
        color: #ffffff !important;
        background: rgba(255,121,0,.16) !important;
    }

    [data-testid="stDialog"] {
        background: linear-gradient(145deg, #151f2b, #0d141c) !important;
        border: 1px solid rgba(255,121,0,.28) !important;
        border-radius: 16px !important;
    }

    [data-testid="stDialog"] h2,
    [data-testid="stDialog"] h3 {
        color: #ffffff !important;
    }

    .summary-lead {
        color: #e7edf5;
        font-size: .9rem;
        line-height: 1.6;
        margin: 5px 0 14px;
    }

    .summary-highlight {
        color: #ffad65;
        font-weight: 750;
    }

    .summary-bullet {
        color: #dce5ee;
        font-size: .82rem;
        line-height: 1.55;
        padding: 5px 0;
        border-bottom: 1px solid rgba(174,190,208,.10);
    }

    .gogig-working {
        display: flex;
        align-items: center;
        gap: 11px;
        margin: 12px 0 15px;
        padding: 10px 0;
        color: #f4f7fb;
        font-size: .82rem;
        font-weight: 650;
    }

    .gogig-working-orbit {
        width: 19px;
        height: 19px;
        flex: 0 0 19px;
        border: 2px solid rgba(255,121,0,.22);
        border-top-color: #ff7900;
        border-right-color: #ffad65;
        border-radius: 50%;
        animation: gogigSpin .85s linear infinite;
        box-shadow: 0 0 13px rgba(255,121,0,.16);
    }

    .gogig-working-copy {
        color: #ffad65;
        letter-spacing: .015em;
    }

    .gogig-working-dots::after {
        content: "";
        display: inline-block;
        width: 18px;
        text-align: left;
        animation: gogigDots 1.35s steps(4, end) infinite;
    }

    @keyframes gogigSpin {
        to { transform: rotate(360deg); }
    }

    @keyframes gogigDots {
        0% { content: ""; }
        25% { content: "."; }
        50% { content: ".."; }
        75%, 100% { content: "..."; }
    }

    @media (prefers-reduced-motion: reduce) {
        .gogig-working-orbit {
            animation: none;
            border-top-color: #ff7900;
        }
        .gogig-working-dots::after {
            animation: none;
            content: "...";
        }
    }
    [data-testid="stAlert"] {
        border-radius: 10px;
        border: 1px solid var(--border);
        font-size: .8rem;
    }
    [data-testid="stProgressBar"] > div {
        background: #26313d;
        border-radius: 20px;
    }
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #16834a, #36c47b);
        border-radius: 20px;
    }

    .progress-track {
        display: flex;
        align-items: flex-start;
        width: 100%;
        margin: 7px 0 5px;
        padding: 0 4px;
    }
    .progress-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 0 0 76px;
        min-width: 0;
        gap: 6px;
    }
    .step-dot {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 23px;
        height: 23px;
        box-sizing: border-box;
        border-radius: 50%;
        background: #202b37;
        border: 1.5px solid #485767;
        color: #aab7c5;
        font-size: 10px;
        font-weight: 750;
    }
    .step-dot.done {
        background: #16834a;
        border-color: #16834a;
        color: #fff;
        box-shadow: 0 0 0 4px rgba(40,181,109,.09);
    }
    .step-dot.active {
        background: rgba(40,181,109,.10);
        border: 2px solid #36c47b;
        color: #7be0a9;
    }
    .step-dot.failed {
        background: #8f2525;
        border-color: #b83b3b;
        color: #fff;
    }
    .progress-line {
        flex: 1 1 auto;
        min-width: 12px;
        height: 2px;
        background: #303c49;
        border-radius: 4px;
        margin: 10px 3px 0;
    }
    .progress-line.done { background: #16834a; }
    .step-label {
        color: #8998a9;
        font-size: .65rem;
        white-space: nowrap;
        text-align: center;
        line-height: 1.2;
    }
    .step-label.done { color: #63d995; font-weight: 700; }
    .step-label.active { color: #8be3b1; font-weight: 750; }
    .step-label.failed { color: #ff8585; font-weight: 750; }

    .plate-number {
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: 3px;
        text-align: center;
        padding: 8px 0;
        color: #ffffff;
        background: transparent;
        border: 0;
        border-bottom: 1px solid rgba(255,121,0,.35);
        border-radius: 0;
        margin: 8px 0;
    }
    .check-card {
        border: 0;
        border-bottom: 1px solid rgba(174,190,208,.13);
        background: transparent;
        border-radius: 0;
        padding: 11px 2px 12px;
        margin: 0;
        min-height: 0;
    }
    .check-title {
        color: #edf3f9;
        font-size: .81rem;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .check-status {
        display: inline-block;
        border-radius: 99px;
        padding: 3px 8px;
        font-size: .63rem;
        font-weight: 750;
        letter-spacing: .06em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .check-status.pass { color: #79e0a7; background: rgba(40,181,109,.13); }
    .check-status.fail { color: #ff9999; background: rgba(220,70,70,.13); }
    .check-status.skipped { color: #f6c77b; background: rgba(230,166,65,.13); }
    .check-status.unknown { color: #c0cbd7; background: rgba(145,160,177,.13); }
    .check-message {
        color: #9eacbc;
        font-size: .72rem;
        line-height: 1.45;
    }
    .footer-credit {
        color: #8795a5;
        font-size: .72rem;
        text-align: right;
    }
    .footer-credit strong { color: #e7edf4; }

    hr {
        border: 0;
        height: 1px;
        background: linear-gradient(90deg, rgba(174,190,208,.02), rgba(174,190,208,.2), rgba(174,190,208,.02));
        margin: 1.45rem 0;
    }

    /* Premium entrance motion: subtle, quick, and respectful of reduced-motion settings. */
    @keyframes lensFadeUp {
        from { opacity: 0; transform: translate3d(0, 13px, 0); }
        to   { opacity: 1; transform: translate3d(0, 0, 0); }
    }

    @keyframes lensGlow {
        0%, 100% { opacity: .55; transform: scaleX(.88); }
        50%      { opacity: 1; transform: scaleX(1); }
    }

    @keyframes lensLogoFloat {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-3px); }
    }

    .topline {
        animation: lensFadeUp .55s ease-out both;
    }

    .brand-hero {
        animation: lensFadeUp .72s cubic-bezier(.2,.7,.2,1) .06s both;
    }

    .brand-logo {
        animation: lensLogoFloat 5s ease-in-out 1s infinite;
    }

    .brand-hero:after {
        transform-origin: center;
        animation: lensGlow 3.8s ease-in-out 1s infinite;
    }

    .eyebrow, .section-title, .section-copy {
        animation: lensFadeUp .55s ease-out both;
    }

    [data-testid="stFileUploader"] {
        transition: border-color .22s ease, background .22s ease, box-shadow .22s ease;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: rgba(255,121,0,.58);
        background: rgba(255,121,0,.025);
        box-shadow: 0 0 0 3px rgba(255,121,0,.045);
    }

    div.stButton > button {
        transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
    }

    div.stButton > button:hover:not(:disabled) {
        transform: translateY(-1px);
    }

    [data-testid="stMetric"] {
        transition: transform .2s ease;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
    }

    .check-card {
        transition: padding-left .2s ease, border-color .2s ease;
    }

    .check-card:hover {
        padding-left: 8px;
        border-bottom-color: rgba(255,121,0,.38);
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
            transition-duration: .01ms !important;
        }
    }

    @media (max-width: 700px) {
        .block-container { padding: .85rem .8rem 1.5rem; }
        .brand-hero { padding: 17px 10px 18px; border-radius: 14px; }
        .brand-logo { width: 112px; }
        .progress-step { flex-basis: 62px; }
        .step-label { font-size: .59rem; }
        .progress-line { min-width: 7px; margin-left: 1px; margin-right: 1px; }
        [data-testid="stMetricValue"] { font-size: 1.25rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

DEFAULT_STATE = {
    "processing_id": None,
    "processing_status": None,
    "status_data": None,
    "analysis": None,
    "uploaded_filename": None,
    "upload_error": None,
    "should_poll": False,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# --------------------------------------------------
# API HELPERS
# --------------------------------------------------

def api_get(path):
    return requests.get(
        f"{API_BASE}{path}",
        timeout=20,
    )


def api_upload(uploaded_file):
    response = requests.post(
        f"{API_BASE}/api/v1/images/upload",
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        },
        timeout=60,
    )

    if not response.ok:
        st.error(f"Upload failed: {response.status_code}")
        st.code(response.text)

    return response

def get_error(response):
    try:
        detail = response.json().get("detail", response.text)

        if isinstance(detail, dict):
            return detail.get("message", str(detail))

        return str(detail)

    except (ValueError, AttributeError):
        return response.text



def refresh_processing(image_id):

    response = api_get(
        f"/api/v1/images/{image_id}/status"
    )

    if not response.ok:
        raise RuntimeError(get_error(response))

    data = response.json()
    current_status = data.get("status")

    st.session_state.processing_status = current_status
    st.session_state.status_data = data

    if current_status == "completed":
        # The status endpoint can report "completed" slightly before the
        # results endpoint makes the analysis payload available. Try once
        # per polling cycle instead of failing the whole job immediately.
        try:
            result_response = api_get(
                f"/api/v1/images/{image_id}/results"
            )

            if result_response.ok:
                result_data = result_response.json()
                analysis = result_data.get("analysis")

                if isinstance(analysis, dict):
                    st.session_state.analysis = analysis

        except (requests.RequestException, ValueError):
            # A temporary results/API response issue is retried by the
            # existing polling loop on its next cycle.
            pass

    elif current_status == "failed":
        st.session_state.analysis = None

    return data



def format_file_size(size):

    if not isinstance(size, (int, float)):
        return "N/A"

    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"

    return f"{size / 1024:.2f} KB"


# --------------------------------------------------
# HORIZONTAL TIMELINE
# --------------------------------------------------

def render_timeline(status):

    steps = [
        "Upload",
        "Validation",
        "Analysis",
        "Results",
    ]

    # Number of completed stages for each backend status.
    completed_count = {
        "pending": 1,
        "processing": 2,
        "completed": 4,
        "failed": 0,
    }.get(status, 1)

    active_index = {
        "pending": 1,
        "processing": 2,
        "completed": None,
        "failed": None,
    }.get(status)

    html = '<div class="progress-track">'

    for index, label in enumerate(steps):

        if status == "failed" and index == 1:
            dot_class = "failed"
            dot_content = "!"
            label_class = "failed"

        elif index < completed_count:
            dot_class = "done"
            dot_content = "&#10003;"
            label_class = "done"

        elif index == active_index:
            dot_class = "active"
            dot_content = str(index + 1)
            label_class = "active"

        else:
            dot_class = ""
            dot_content = str(index + 1)
            label_class = ""

        html += f"""
        <div class="progress-step">
            <div class="step-dot {dot_class}">{dot_content}</div>
            <div class="step-label {label_class}">{label}</div>
        </div>
        """

        if index < len(steps) - 1:
            line_class = "done" if index < completed_count else ""
            html += f'<div class="progress-line {line_class}"></div>'

    html += "</div>"

    st.markdown(html, unsafe_allow_html=True)

    if status == "completed":
        st.success("Image analysis completed successfully.")
    elif status == "failed":
        st.error("Image processing failed.")
    elif status == "processing":
        st.info("Analyzing image. Please wait...")
    else:
        st.caption("Waiting for image processing...")


# --------------------------------------------------
# RESULT HELPERS
# --------------------------------------------------

def show_check(title, check):
    import html

    if not isinstance(check, dict):
        check = {}

    status = str(check.get("status", "unknown")).lower()
    if status not in ("pass", "fail", "skipped"):
        status = "unknown"

    label = {
        "pass": "Passed",
        "fail": "Failed",
        "skipped": "Skipped",
        "unknown": "Inconclusive",
    }[status]

    message = html.escape(str(check.get("message", "No details available.")))
    safe_title = html.escape(str(title))

    st.markdown(
        f"""
        <div class="check-card">
            <div class="check-title">{safe_title}</div>
            <div class="check-status {status}">{label}</div>
            <div class="check-message">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_number_plate(check):

    st.markdown("### Number plate")

    if not isinstance(check, dict):
        st.info("Number plate information unavailable.")
        return

    candidates = check.get("candidates", [])
    status = check.get("status", "unknown")

    if not candidates:
        st.warning("No reliable number plate detected.")
        return

    best = candidates[0]

    if status == "pass":
        st.success("Number plate recognized")
    else:
        st.warning(
            "Possible number plate detected. Manual verification required."
        )

    st.markdown(
        f'<div class="plate-number">{best.get("plate", "Unknown")}</div>',
        unsafe_allow_html=True,
    )

    confidence = best.get("candidate_confidence")

    if confidence is not None:
        st.caption(
            f"Candidate confidence: {confidence * 100:.1f}%"
        )

    a, b = st.columns(2)

    with a:
        st.write(f"**Series:** {best.get('series', 'N/A')}")
        st.write(
            f"**State:** {best.get('state_code') or 'N/A'}"
        )

    with b:
        st.write(
            f"**District:** {best.get('district_code') or 'N/A'}"
        )
        st.write(
            f"**Direct OCR match:** "
            f"{'Yes' if best.get('direct_ocr_match') else 'No'}"
        )


# --------------------------------------------------
# MORE DETAILS
# --------------------------------------------------

def render_more_details(analysis):

    checks = analysis.get("checks", {})
    image = analysis.get("image", {})
    summary = analysis.get("summary", {})

    # Streamlit does not support nested expanders. Keep all detail sections
    # inside this single expander and use compact headings instead.
    with st.expander("More details"):

        st.markdown("**Image metadata**")

        a, b, c = st.columns(3)

        with a:
            st.caption(f"Width: {image.get('width', 'N/A')} px")
            st.caption(f"Height: {image.get('height', 'N/A')} px")

        with b:
            st.caption(
                f"File size: {format_file_size(image.get('file_size'))}"
            )

        with c:
            st.caption(
                f"Schema version: {analysis.get('schema_version', 'N/A')}"
            )

        st.divider()
        st.markdown("**Individual check metrics**")

        for key, check in checks.items():

            if not isinstance(check, dict):
                continue

            st.markdown(f"**{key.replace('_', ' ').title()}**")
            st.caption(
                f"Status: {check.get('status', 'N/A')} · "
                f"{check.get('message', 'No message available.')}"
            )

            metrics = []
            for metric, value in check.items():
                if metric in (
                    "status", "passed", "message", "phash",
                    "lines", "candidates", "text"
                ):
                    continue
                metrics.append(
                    f"{metric.replace('_', ' ').title()}: {value}"
                )

            if metrics:
                st.caption(" · ".join(metrics))

        st.divider()
        st.markdown("**Extracted OCR lines**")

        ocr = checks.get("ocr", {})
        lines = ocr.get("lines", [])

        if lines:
            for line in lines:
                st.caption(
                    f"• {line.get('text', '')} · "
                    f"Confidence: {line.get('confidence', 0) * 100:.1f}%"
                )
        else:
            st.caption("No OCR lines available.")

        st.divider()
        st.markdown("**Additional number plate candidates**")

        plate_check = checks.get("number_plate", {})
        candidates = plate_check.get("candidates", [])

        if candidates:
            for candidate in candidates:
                st.write(f"**{candidate.get('plate', 'Unknown')}**")
                st.caption(
                    f"Confidence: "
                    f"{candidate.get('candidate_confidence', 0) * 100:.1f}%"
                    f" · Source: {candidate.get('source_region', 'N/A')}"
                    f" · Preprocessing: {candidate.get('preprocessing', 'N/A')}"
                )
        else:
            st.caption("No candidates available.")

        st.divider()
        st.markdown("**Summary and limitations**")

        st.caption(
            f"Evaluated checks: {summary.get('evaluated_checks', 0)}"
        )

        for key in (
            "flagged_checks",
            "unknown_checks",
            "skipped_checks",
        ):
            values = summary.get(key, [])
            if values:
                st.caption(
                    f"{key.replace('_', ' ').title()}: "
                    + ", ".join(values)
                )

        for item in analysis.get("limitations", []):
            st.caption(f"• {item}")


# --------------------------------------------------
# QUICK RESULTS SUMMARY POPUP
# --------------------------------------------------

@st.dialog("gOGig · Quick summary", width="small")
def show_quick_summary(analysis):
    checks = analysis.get("checks", {}) or {}
    summary = analysis.get("summary", {}) or {}
    image = analysis.get("image", {}) or {}

    passed = summary.get("checks_passed", 0)
    failed = summary.get("checks_failed", 0)
    unknown = summary.get("checks_unknown", 0)
    total = summary.get("total_checks", 0)

    st.markdown(
        '<div class="eyebrow">INSPECTION COMPLETE</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="summary-lead">'
        'Your image has been processed. Here is the key outcome at a glance.'
        '</div>',
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Passed", passed)
    with metric_cols[1]:
        st.metric("Failed", failed)
    with metric_cols[2]:
        st.metric("Unknown", unknown)

    st.caption(f"{total} total checks · {image.get('width', 'N/A')} × {image.get('height', 'N/A')} px")

    highlights = [
        ("Blur detection", checks.get("blur", {})),
        ("Brightness", checks.get("brightness", {})),
        ("Duplicate detection", checks.get("duplicate_fingerprint", {})),
        ("OCR extraction", checks.get("ocr", {})),
        ("Image dimensions", checks.get("dimensions", {})),
        ("Number plate", checks.get("number_plate", {})),
    ]

    st.markdown("**Key findings**")
    for label, item in highlights:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "unknown")).upper()
        message = item.get("message", "No additional information.")
        st.markdown(
            f'<div class="summary-bullet">'
            f'<span class="summary-highlight">{label}</span>'
            f' &nbsp;·&nbsp; {status}<br>{message}'
            f'</div>',
            unsafe_allow_html=True,
        )

    plate_candidates = checks.get("number_plate", {}).get("candidates", [])
    if plate_candidates:
        plate = plate_candidates[0].get("plate", "Unknown")
        st.markdown("**Detected plate candidate**")
        st.markdown(
            f'<div class="plate-number">{plate}</div>',
            unsafe_allow_html=True,
        )
        st.caption("Verify the candidate manually if recognition is marked inconclusive.")

    st.caption(
        "This is an automated screening summary, not a guarantee of image authenticity."
    )


# --------------------------------------------------
# HEADER
# --------------------------------------------------

logo_path = Path(__file__).with_name("gogig_logo_dark.png")

if logo_path.exists():
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    logo_html = (
        f'<img class="brand-logo" '
        f'src="data:image/png;base64,{logo_b64}" alt="gOGig official logo">'
    )
else:
    logo_html = (
        '<div style="color:#ffffff;font-weight:800;font-size:1.35rem;">'
        'g<span style="color:#ff7900;">OG</span>ig</div>'
    )

st.markdown(
    """
    <div class="topline">
        <span><strong>GINGER MEDIA GROUP</strong> &nbsp; / &nbsp; INTELLIGENT MEDIA</span>
        <span class="live">● SYSTEM READY</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="brand-hero">
        {logo_html}
        <div class="brand-product">LENS<span>.</span></div>
        <div class="brand-subtitle">Smart image analysis. Reliable processing.</div>
        <div class="brand-chip">Intelligent media processing platform</div>
    </div>
    """,
    unsafe_allow_html=True,
)



@st.dialog("Full image preview", width="large")
def show_full_image(image_bytes):
    full_image = Image.open(BytesIO(image_bytes))
    st.image(full_image, use_container_width=True)


# --------------------------------------------------
# UPLOAD SECTION
# --------------------------------------------------

st.markdown('<div class="eyebrow">01 / INPUT</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Inspect an image</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-copy">Upload a vehicle image to run quality validation, duplicate screening, OCR and number plate recognition.</div>',
    unsafe_allow_html=True,
)

upload_col, preview_col = st.columns([1.2, 0.8], gap="large")

with upload_col:
    with upload_col:
        uploaded = st.file_uploader(
            "Select image",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=False,
            label_visibility="collapsed",
        )

        if uploaded:
            st.caption(
                f"Selected: **{uploaded.name}** · "
                f"{format_file_size(uploaded.size)}"
            )
        else:
            st.caption(
                "JPG · JPEG · PNG · WEBP / "
                "File and image limits are validated by the API."
            )

        
        is_processing = (
            st.session_state.processing_id is not None
            and st.session_state.processing_status in (
                "pending",
                "processing",
            )
        )

        analyze_clicked = st.button(
            "Run image analysis  →",
            type="primary",
            disabled=uploaded is None or is_processing,
            use_container_width=True,
        )

        st.markdown(
            """
            <p style="
                text-align: center;
                color: #ffb16f;
                font-size: 12px;
                margin-top: -8px;
                font-style: italic;
            ">
                ⏳ Wait 10 seconds… good things take time.
                Even AI needs a coffee break! ☕🤖
            </p>
            """,
            unsafe_allow_html=True,
        )

with preview_col:
    if uploaded:
        # Fixed 16:9 thumbnail keeps portrait uploads from stretching the page.
        image_bytes = uploaded.getvalue()
        original_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        preview_image = ImageOps.fit(
            original_image,
            (480, 270),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        st.image(preview_image, use_container_width=True)

        if st.button(
            "View full image  ↗",
            key="open_full_image_preview",
            use_container_width=True,
        ):
            show_full_image(image_bytes)
    else:
        st.markdown(
            """
            <div style="
                height:150px; display:flex; flex-direction:column;
                align-items:center; justify-content:center; text-align:center;
                border:1px dashed rgba(159,177,198,.22); border-radius:8px;
                background:rgba(255,255,255,.012); color:#8291a2; padding:12px;
                box-sizing:border-box;">
                <div style="font-size:1.55rem; margin-bottom:5px; color:#ff7900;">＋</div>
                <div style="font-size:.78rem; font-weight:650; color:#c2ccd7;">Image preview</div>
                <div style="font-size:.68rem; margin-top:3px;">Fixed preview · Full image on demand</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

if analyze_clicked and uploaded:

    # Reset state only when starting a genuinely new upload.
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value

    try:
        with st.spinner("Uploading image..."):
            response = api_upload(uploaded)

        if response.status_code != 202:
            st.session_state.upload_error = get_error(response)

        else:
            payload = response.json()

            st.session_state.processing_id = payload["processing_id"]
            st.session_state.processing_status = payload["status"]
            st.session_state.uploaded_filename = uploaded.name
            st.session_state.should_poll = True

    except requests.RequestException as exc:
        st.session_state.upload_error = str(exc)

    except (ValueError, KeyError) as exc:
        st.session_state.upload_error = str(exc)


if st.session_state.upload_error:
    st.error(st.session_state.upload_error)



# PROCESSING TIMELINE


if st.session_state.processing_id:

    st.markdown(
        '<div class="eyebrow">02 / LIVE WORKFLOW</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section-title">Processing progress</div>',
        unsafe_allow_html=True
    )

    st.caption(
        f"Job ID · {st.session_state.processing_id}"
    )

    render_timeline(
        st.session_state.processing_status or "pending"
    )

    # --------------------------------------------------
    # AUTOMATIC POLLING
    # --------------------------------------------------

    if st.session_state.should_poll:

        working_indicator = st.empty()

        working_indicator.markdown(
            """
            <div class="gogig-working">
                <span class="gogig-working-orbit"></span>
                <span class="gogig-working-copy">
                    gOGig is working
                    <span class="gogig-working-dots"></span>
                </span>
                <span style="color:#91a0b1;font-weight:400;">
                    Validating and analyzing your image
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        polling_error = None
        job_finished = False

        for attempt in range(MAX_POLL_ATTEMPTS):

            try:
                status_data = refresh_processing(
                    st.session_state.processing_id
                )

                current_status = status_data.get("status")

                # A completed status is not enough: wait until the actual
                # analysis payload is available before stopping the poller.
                if current_status == "failed":
                    job_finished = True
                    break

                if (
                    current_status == "completed"
                    and isinstance(st.session_state.analysis, dict)
                ):
                    job_finished = True
                    break

            except (
                requests.RequestException,
                RuntimeError
            ) as exc:

                polling_error = str(exc)
                break

            time.sleep(POLL_INTERVAL)

        working_indicator.empty()

        if polling_error:

            st.session_state.upload_error = polling_error
            st.session_state.should_poll = False

        elif job_finished:

            st.session_state.should_poll = False

        else:

            # Do not lose the current job when polling reaches
            # its automatic time limit.
            st.session_state.should_poll = False

        st.rerun()

    # --------------------------------------------------
    # MANUAL REFRESH FOR EXISTING JOB
    # --------------------------------------------------

    if (
        st.session_state.processing_status in ("pending", "processing")
        or (
            st.session_state.processing_status == "completed"
            and not isinstance(st.session_state.analysis, dict)
        )
    ):

        if st.session_state.processing_status == "completed":
            st.info(
                "Processing is complete. The result is being prepared. "
                "Refresh this existing job to retrieve it without uploading again."
            )
        else:
            st.info(
                "Your image is still being processed. "
                "You can check the existing job without uploading again."
            )

        if st.button(
            "Refresh status ↻",
            key="refresh_existing_job",
            use_container_width=False
        ):

            st.session_state.should_poll = True
            st.rerun()

# --------------------------------------------------
# RESULTS SECTION
# --------------------------------------------------

if st.session_state.processing_status == "completed":

    analysis = st.session_state.analysis

    if isinstance(analysis, dict):

        checks = analysis.get("checks", {})
        summary = analysis.get("summary", {})
        image = analysis.get("image", {})

        results_heading, summary_action = st.columns([3, 1], vertical_alignment="center")

        with results_heading:
            st.markdown('<div class="eyebrow">03 / INSPECTION REPORT</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Analysis results</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-copy">A consolidated view of image quality, duplicate screening, text extraction and number plate recognition.</div>',
                unsafe_allow_html=True,
            )

        with summary_action:
            st.markdown('<div class="summary-trigger">', unsafe_allow_html=True)
            if st.button("✦ Quick summary", key="open_quick_summary", use_container_width=True):
                show_quick_summary(analysis)
            st.markdown('</div>', unsafe_allow_html=True)

        a, b, c, d = st.columns(4)
        with a:
            st.metric("Passed", summary.get("checks_passed", 0))
        with b:
            st.metric("Failed", summary.get("checks_failed", 0))
        with c:
            st.metric("Inconclusive", summary.get("checks_unknown", 0))
        with d:
            st.metric("Total checks", summary.get("total_checks", 0))

        confidence = summary.get("confidence", 0)
        try:
            confidence_value = max(0.0, min(float(confidence), 1.0))
        except (TypeError, ValueError):
            confidence_value = 0.0

        st.progress(
            confidence_value,
            text=f"Screening confidence · {confidence_value * 100:.1f}% of evaluated checks passed",
        )
        st.caption(
            "Screening confidence is a checks-passed ratio, not a calibrated probability."
        )

        st.markdown("#### Core assignment checks")

        left, right = st.columns(2, gap="medium")
        with left:
            show_check("Blur detection", checks.get("blur", {}))
            show_check("Brightness / low-light analysis", checks.get("brightness", {}))
            show_check("Image dimensions validation", checks.get("dimensions", {}))

        with right:
            show_check("Duplicate image detection", checks.get("duplicate_fingerprint", {}))
            show_check("OCR text extraction", checks.get("ocr", {}))

        st.markdown("#### Indian number plate recognition")
        render_number_plate(checks.get("number_plate", {}))

        st.markdown("#### Image information")
        info_a, info_b, info_c = st.columns(3)
        with info_a:
            st.caption("DIMENSIONS")
            st.markdown(
                f"**{image.get('width', 'N/A')} × {image.get('height', 'N/A')} px**"
            )
        with info_b:
            st.caption("FILE SIZE")
            st.markdown(f"**{format_file_size(image.get('file_size'))}**")
        with info_c:
            st.caption("ANALYZER VERSION")
            st.markdown(f"**{analysis.get('schema_version', 'N/A')}**")

        render_more_details(analysis)

    else:
        st.warning("Analysis response is unavailable.")

elif st.session_state.processing_status == "failed":

    status_data = st.session_state.status_data or {}

    st.error(
        status_data.get("error")
        or "Image processing failed."
    )

    if status_data.get("error_code"):
        st.caption(f"Error code: {status_data['error_code']}")



# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("---")
footer_left, footer_right = st.columns([3, 1])

with footer_left:
    st.caption(
        "gOGig Lens · Intelligent media processing · Screening assistance only."
    )

with footer_right:
    st.markdown(
        '<div class="footer-credit">Crafted by <strong>Mayank Patidar</strong></div>',
        unsafe_allow_html=True,
    )
