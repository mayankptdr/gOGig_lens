import os
import time
import requests
import streamlit as st
from datetime import datetime

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="MediaGuard AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --bg:#090d18; --panel:#111827; --panel2:#151f31; --line:#263247; --muted:#91a0b8; --text:#edf3ff; --cyan:#57d6e8; --violet:#9b8cff; }
.stApp { background: radial-gradient(ellipse at 15% 0%, #182443 0%, #0b1120 38%, #080c16 100%); color:var(--text); font-family:'DM Sans',sans-serif; }
[data-testid="stSidebar"] { background:#0b1220; border-right:1px solid var(--line); }
h1,h2,h3,.brand { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-.04em; }
.block-container { padding-top:2rem; max-width:1440px; }
.brand { font-size:1.45rem; font-weight:700; color:#f4f7ff; }
.brand span { color:var(--cyan); }
.eyebrow { color:var(--cyan); text-transform:uppercase; letter-spacing:.16em; font-size:.72rem; font-weight:700; }
.hero { padding:1.5rem 1.7rem; border:1px solid #2a3b56; border-radius:18px; background:linear-gradient(115deg,rgba(36,57,91,.78),rgba(20,28,47,.72)); margin-bottom:1.2rem; }
.hero h1 { font-size:2.35rem; margin:.35rem 0 .25rem; color:#f5f8ff; }
.hero p { color:#aebbd0; margin:0; }
.metric { background:linear-gradient(145deg,#151f31,#101827); border:1px solid #28364c; padding:1rem 1.1rem; border-radius:15px; min-height:108px; }
.metric-label { color:#95a5bf; font-size:.78rem; }
.metric-value { color:#f5f8ff; font-family:'Space Grotesk'; font-size:1.8rem; font-weight:700; margin-top:.3rem; }
.panel { background:rgba(17,24,39,.88); border:1px solid #29364b; border-radius:16px; padding:1.15rem 1.25rem; }
.small-muted { color:#91a0b8; font-size:.86rem; }
div[data-testid="stFileUploader"] { background:#111a2a; border:1px dashed #526580; border-radius:14px; padding:1rem; }
.stButton>button { border-radius:10px; border:1px solid #4a7c94; background:linear-gradient(100deg,#176b83,#5142a8); color:white; font-weight:700; padding:.55rem 1rem; }
.stButton>button:hover { border-color:#75e5f2; color:white; }
div[data-testid="stTextInput"] input { background:#111a2a; color:#edf3ff; border:1px solid #34445d; border-radius:9px; }
hr { border-color:#263247; }
[data-testid="stMetric"] { background:#131d2d; border:1px solid #29364b; border-radius:12px; padding:12px; }
</style>
""", unsafe_allow_html=True)

def api_get(path):
    return requests.get(f"{API_BASE}{path}", timeout=20)

def metric(label, value, note):
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="small-muted">{note}</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand">🛡️ MediaGuard<span> AI</span></div>', unsafe_allow_html=True)
    st.caption("INTELLIGENT MEDIA SCREENING")
    page = st.radio("WORKSPACE", ["Overview", "Analyze image", "Track processing"], label_visibility="visible")
    st.divider()
    st.markdown("**SYSTEM STATUS**")
    try:
        health = api_get("/health")
        if health.ok:
            st.success("API connected")
        else:
            st.warning(f"API responded: {health.status_code}")
    except requests.RequestException:
        st.error("API unavailable")
    st.caption(f"API endpoint: {API_BASE}")
    st.divider()
    st.caption("Backend: FastAPI · Worker: RQ · CV: OpenCV")

if page == "Overview":
    st.markdown('<div class="hero"><div class="eyebrow">FIELD IMAGE INTELLIGENCE</div><h1>See what your images are hiding.</h1><p>Screen vehicle media for quality issues, visual similarity and registration-text signals — with transparent, explainable checks.</p></div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric("PROCESSING ENGINE", "Async", "Queue-based analysis")
    with c2: metric("IMAGE QUALITY", "CV", "Blur · brightness · dimensions")
    with c3: metric("SIMILARITY", "pHash", "Near-duplicate fingerprinting")
    with c4: metric("RESULT FORMAT", "JSON", "Structured, explainable output")
    st.write("")
    left,right = st.columns([1.25, .75], gap="large")
    with left:
        st.markdown('<div class="panel"><div class="eyebrow">HOW IT WORKS</div><h3>From upload to insight</h3><p class="small-muted">Every image receives a processing ID immediately. Analysis runs in a background worker, so the API remains responsive.</p></div>', unsafe_allow_html=True)
        steps = [("01","Upload & validate","Supported image formats and size checks"),("02","Queue processing","Metadata is stored and a background job is created"),("03","Analyze signals","OpenCV quality checks and similarity fingerprint"),("04","Review findings","Status, flags, metrics and limitations")]
        for n,title,desc in steps:
            st.markdown(f'<div class="panel" style="margin-top:9px;padding:.85rem 1rem"><b style="color:#57d6e8">{n}</b> &nbsp; <b>{title}</b><div class="small-muted" style="margin-left:2.4rem">{desc}</div></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="eyebrow">SCREENING PRINCIPLE</div><h3>Evidence, not assumptions.</h3><p class="small-muted">MediaGuard AI reports heuristic signals. A flag is a prompt for review — not proof of fraud, tampering or authenticity.</p></div>', unsafe_allow_html=True)
        st.info("Tip: Start with Analyze image to upload a vehicle photo and receive its processing ID.")

elif page == "Analyze image":
    st.markdown('<div class="eyebrow">NEW ANALYSIS</div><h1>Analyze an image</h1><p class="small-muted">Upload a JPEG, PNG or WEBP image. The API accepts the file and processes it asynchronously.</p>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Drop vehicle image here", type=["jpg","jpeg","png","webp"], accept_multiple_files=False)
    if uploaded:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)
        st.caption(f"{uploaded.type or 'image'} · {uploaded.size/1024:.1f} KB")
    col1,col2 = st.columns([1,2])
    with col1:
        submit = st.button("Run image analysis", disabled=uploaded is None, use_container_width=True)
    with col2:
        auto_refresh = st.checkbox("Wait for result automatically", value=True)
    if submit and uploaded:
        try:
            response = requests.post(
                f"{API_BASE}/api/v1/images/upload",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                timeout=60,
            )
            if response.status_code != 202:
                st.error(f"Upload failed ({response.status_code}): {response.text}")
            else:
                payload = response.json()
                image_id = payload["processing_id"]
                st.session_state["last_processing_id"] = image_id
                st.success("Image accepted. Processing ID created.")
                st.code(image_id)
                if auto_refresh:
                    status_box = st.empty()
                    progress = st.progress(5)
                    final_status = None
                    for i in range(60):
                        sr = api_get(f"/api/v1/images/{image_id}/status")
                        if sr.ok:
                            final_status = sr.json()
                            status_box.info(f"Processing status: {final_status['status']}")
                            progress.progress(min(95, 5 + i*2))
                            if final_status["status"] in ("completed","failed"):
                                break
                        time.sleep(2)
                    if final_status and final_status["status"] == "completed":
                        rr = api_get(f"/api/v1/images/{image_id}/results")
                        if rr.ok:
                            progress.progress(100)
                            st.success("Analysis completed.")
                            st.json(rr.json()["analysis"])
                        else:
                            st.warning(rr.text)
                    elif final_status and final_status["status"] == "failed":
                        st.error(final_status.get("error") or "Processing failed")
                    else:
                        st.warning("Still processing. Use Track processing with the ID above.")
        except requests.RequestException as exc:
            st.error(f"Could not reach API: {exc}")

else:
    st.markdown('<div class="eyebrow">JOB MONITOR</div><h1>Track processing</h1><p class="small-muted">Look up the status and structured analysis for an uploaded image.</p>', unsafe_allow_html=True)
    default_id = st.session_state.get("last_processing_id", "")
    image_id = st.text_input("Processing ID", value=default_id, placeholder="Paste processing UUID")
    a,b = st.columns([1,1])
    with a: check_status = st.button("Refresh status", use_container_width=True)
    with b: check_results = st.button("Fetch analysis results", use_container_width=True)
    if check_status and image_id:
        try:
            r = api_get(f"/api/v1/images/{image_id}/status")
            if r.ok:
                data = r.json()
                st.success(f"Status: {data['status'].upper()}")
                st.json(data)
            else:
                st.error(f"{r.status_code}: {r.text}")
        except requests.RequestException as exc:
            st.error(str(exc))
    if check_results and image_id:
        try:
            r = api_get(f"/api/v1/images/{image_id}/results")
            if r.ok:
                data = r.json()
                st.success("Analysis results")
                analysis = data.get("analysis", {})
                summary = analysis.get("summary", {})
                m1,m2,m3 = st.columns(3)
                with m1: st.metric("Checks passed", f"{summary.get('checks_passed','—')}/{summary.get('checks_total','—')}")
                with m2: st.metric("Screening score", summary.get("confidence_score","—"))
                with m3: st.metric("Flagged checks", len(summary.get("flagged_checks", [])))
                st.json(analysis)
            else:
                st.error(f"{r.status_code}: {r.text}")
        except requests.RequestException as exc:
            st.error(str(exc))

st.divider()
st.caption("MediaGuard AI · Screening assistance only. Heuristic signals do not establish fraud or authenticity.")
