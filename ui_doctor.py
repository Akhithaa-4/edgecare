import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import json
from collections import deque


# ============================================================================
# CONFIGURATION
# ============================================================================


API_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 300  # Increased for Ollama initialization


# ============================================================================
# PAGE CONFIG
# ============================================================================


st.set_page_config(
    page_title="EdgeCare - Doctor Dashboard",
    page_icon="👨⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# STYLING
# ============================================================================


st.markdown("""
<style>
    :root {
        --primary-color: #1f77b4;
        --secondary-color: #ff7f0e;
        --danger-color: #d62728;
        --success-color: #2ca02c;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    
    .high-risk { background-color: #ffebee; }
    .medium-risk { background-color: #fff3e0; }
    .low-risk { background-color: #e8f5e9; }
    
    .audit-log-container {
        background-color: #f5f5f5;
        border-left: 4px solid #1f77b4;
        padding: 10px;
        margin: 5px 0;
        border-radius: 4px;
        font-family: monospace;
        font-size: 12px;
        line-height: 1.6;
    }
    
    .escalation-alert {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================


def init_session_state():
    """Initialize all session state variables"""
    if 'audit_log' not in st.session_state:
        st.session_state.audit_log = deque(maxlen=100)  # Store last 100 events
    
    if 'auto_escalate_tracking' not in st.session_state:
        st.session_state.auto_escalate_tracking = {}  # Track wait times per patient
    
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = datetime.now()
    
    if 'escalation_threshold_minutes' not in st.session_state:
        st.session_state.escalation_threshold_minutes = 15  # Auto-escalate after 15 min


init_session_state()


# ============================================================================
# AUDIT LOG MANAGEMENT
# ============================================================================


def add_audit_log(action, patient_id=None, details="", severity="INFO"):
    """Add event to audit log - FILTERS OUT SPAM"""
    # SKIP SPAM EVENTS (every 5s)
    if action in ["QUEUE_FETCH", "QUEUE_REFRESH", "DATA_FETCH"]:
        return  # ← SILENTLY SKIP
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = {
        "timestamp": timestamp,
        "action": action,
        "patient_id": patient_id,
        "details": details,
        "severity": severity
    }
    
    st.session_state.audit_log.appendleft(log_entry)
    print(f"[{timestamp}] {severity}: {action} | Patient: {patient_id} | {details}")



def display_audit_log():
    """Display audit log in UI"""
    st.subheader("📋 Audit Log")
    
    if len(st.session_state.audit_log) == 0:
        st.info("No audit events yet")
        return
    
    # Create a table-like display
    log_df = pd.DataFrame(list(st.session_state.audit_log))
    
    # Color code by severity
    severity_colors = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ESCALATION": "🚨",
        "SUCCESS": "✅"
    }
    
    for idx, row in log_df.iterrows():
        icon = severity_colors.get(row['severity'], "📝")
        
        col1, col2, col3 = st.columns([1, 2, 3])
        
        with col1:
            st.caption(f"{icon} {row['severity']}")
        
        with col2:
            st.caption(row['timestamp'])
        
        with col3:
            if pd.notna(row['patient_id']):
                st.caption(f"**{row['action']}** | Patient: `{row['patient_id'][:8]}...` | {row['details']}")
            else:
                st.caption(f"**{row['action']}** | {row['details']}")


# ============================================================================
# HELPER FUNCTIONS - WITH ERROR HANDLING
# ============================================================================


def check_backend_health():
    """Check if backend is running and healthy"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            timeout=REQUEST_TIMEOUT
        )
        return response.status_code == 200
    except requests.exceptions.Timeout:
        st.warning(f"⚠️ Backend is responding slowly (>{REQUEST_TIMEOUT}s timeout)")
        st.info("This is normal if Ollama is initializing. Please wait...")
        return False
    except Exception as e:
        st.error(f"❌ Backend health check failed: {str(e)}")
        st.info(f"📌 Make sure backend is running: `python backend.py` on port 8000")
        return False


def fetch_queue():
    """Fetch patient queue from backend - NO SPAM LOGGING"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/queue",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        # ✅ NO MORE QUEUE_FETCH LOGGING (every 5s spam removed)
        queue_data = response.json()
        
        # NEW: Detect NEW patients only (not every fetch)
        if 'previous_patient_ids' not in st.session_state:
            st.session_state.previous_patient_ids = set()
            
        current_patient_ids = {p['patient_id'] for p in queue_data}
        new_patients = current_patient_ids - st.session_state.previous_patient_ids
        
        # Log ONLY new patients (not every fetch)
        for patient_id in new_patients:
            add_audit_log("PATIENT_ADDED", patient_id, "New patient in queue", "INFO")
            
        st.session_state.previous_patient_ids = current_patient_ids
        
        return queue_data
        
    except requests.exceptions.ConnectionError:
        st.error("❌ **Connection Failed**: Cannot reach backend at 127.0.0.1:8000")
        st.warning("⚠️ **Steps to fix:**")
        st.write("""
        1. Open a **NEW terminal window**
        2. Navigate to your project folder
        3. Run: `python backend.py`
        4. Wait for message: "🚀 Starting on http://localhost:8000"
        5. Then run this Streamlit app in another terminal
        """)
        add_audit_log("BACKEND_CONNECTION_FAILED", details="Cannot reach backend", severity="WARNING")
        return None
        
    except requests.exceptions.Timeout:
        st.error(f"❌ Backend timeout (>{REQUEST_TIMEOUT}s). Backend might be initializing.")
        st.info("If you see Ollama initialization messages in backend terminal, this is normal. Try again in a few seconds.")
        add_audit_log("BACKEND_TIMEOUT", details="Backend slow to respond", severity="WARNING")
        return None
        
    except Exception as e:
        st.error(f"❌ Error fetching queue: {str(e)}")
        add_audit_log("QUEUE_FETCH_ERROR", details=f"{str(e)}", severity="WARNING")
        return None

def fetch_queue_state():
    """Fetch queue state/analytics"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/queue/state",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"Could not load queue state: {str(e)}")
        return None


def fetch_analytics():
    """Fetch analytics data"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/queue/analytics",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"Could not load analytics: {str(e)}")
        return None


def escalate_patient(patient_id, new_risk_level, reason=""):
    """Escalate patient risk level"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/queue/escalate/{patient_id}",
            params={
                "new_risk_level": new_risk_level,
                "reason": reason
            },
            timeout=REQUEST_TIMEOUT
        )

        
        # Log escalation
        add_audit_log(
            "ESCALATION",
            patient_id=patient_id,
            details=f"Escalated to {new_risk_level}. Reason: {reason}",
            severity="ESCALATION"
        )
        
        return response.json()
    except Exception as e:
        error_msg = f"Error escalating patient: {str(e)}"
        st.error(error_msg)
        add_audit_log(
            "ESCALATION_FAILED",
            patient_id=patient_id,
            details=error_msg,
            severity="WARNING"
        )
        return None


def mark_patient_seen(patient_id):
    """Mark patient as seen"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/queue/mark-seen/{patient_id}",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        # Log patient seen
        add_audit_log(
            "PATIENT_SEEN",
            patient_id=patient_id,
            details="Patient marked as seen",
            severity="SUCCESS"
        )
        
        return response.json()
    except Exception as e:
        error_msg = f"Error marking patient as seen: {str(e)}"
        st.error(error_msg)
        add_audit_log(
            "PATIENT_SEEN_FAILED",
            patient_id=patient_id,
            details=error_msg,
            severity="WARNING"
        )
        return None


# ============================================================================
# AUTO-ESCALATION LOGIC
# ============================================================================


def check_and_auto_escalate(df):
    """Check wait times and auto-escalate if threshold exceeded"""
    escalations_made = 0
    
    if df is None or len(df) == 0:
        return escalations_made
    
    current_time = datetime.now()
    threshold_minutes = st.session_state.escalation_threshold_minutes
    
    for idx, patient in df.iterrows():
        patient_id = patient['patient_id']
        current_risk = patient['risk_level']
        
        # Parse patient added timestamp (adjust based on your data format)
        try:
            patient_added_time = datetime.fromisoformat(patient.get('added_at', datetime.now().isoformat()))
        except:
            patient_added_time = current_time
        
        wait_time_minutes = (current_time - patient_added_time).total_seconds() / 60
        
        # Auto-escalation logic
        if current_risk == 'LOW' and wait_time_minutes > threshold_minutes:
            escalate_patient(patient_id, 'MEDIUM', f"Auto-escalated due to {wait_time_minutes:.1f} min wait time")
            escalations_made += 1
            
        elif current_risk == 'MEDIUM' and wait_time_minutes > (threshold_minutes * 1.5):
            escalate_patient(patient_id, 'HIGH', f"Auto-escalated due to {wait_time_minutes:.1f} min wait time")
            escalations_made += 1
        
        elif current_risk == 'HIGH' and wait_time_minutes > (threshold_minutes * 2):
            escalate_patient(patient_id, 'CRITICAL', f"Auto-escalated due to {wait_time_minutes:.1f} min wait time")
            escalations_made += 1
    
    if escalations_made > 0:
        st.markdown(f"<div class='escalation-alert'>🚨 Auto-escalated {escalations_made} patient(s) due to excessive wait time</div>", unsafe_allow_html=True)
    
    return escalations_made


# ============================================================================
# HEADER
# ============================================================================


col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("# 👨⚕️ EdgeCare Doctor Dashboard")

st.markdown("---")


# ============================================================================
# MAIN CONTENT
# ============================================================================


queue_data = fetch_queue()

if queue_data is None:
    st.stop()

# Convert to DataFrame for better display
df = pd.DataFrame(queue_data)

# ============================================================================
# AUTO-ESCALATION CHECK
# ============================================================================

if len(df) > 0:
    check_and_auto_escalate(df)

if len(df) == 0:
    st.info("📊 No patients in queue")
else:
    # Organize by risk level
    st.subheader("📋 Patient Queue (Priority Order)")
    
    high_risk = df[df['risk_level'] == 'HIGH']
    medium_risk = df[df['risk_level'] == 'MEDIUM']
    low_risk = df[df['risk_level'] == 'LOW']
    critical_risk = df[df['risk_level'] == 'CRITICAL']
    
    # CRITICAL Risk Section (NEW)
    if len(critical_risk) > 0:
        st.markdown("### 🔴🔴 CRITICAL (Immediate Emergency)")
        for idx, patient in critical_risk.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Seen", key=f"seen_{patient['patient_id']}", help="Mark patient as seen"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
            
            with col5:
                if st.button("⬇️ Lower", key=f"lower_{patient['patient_id']}", help="Lower risk level"):
                    escalate_patient(patient['patient_id'], 'HIGH', "Doctor manually lowered risk")
                    st.info("Risk lowered")
                    time.sleep(1)
                    st.rerun()
    
    # High Risk Section
    if len(high_risk) > 0:
        st.markdown("### 🔴 High Risk (Immediate Attention)")
        for idx, patient in high_risk.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Seen", key=f"seen_{patient['patient_id']}", help="Mark patient as seen"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
            
            with col5:
                if st.button("🚨 Escalate", key=f"escalate_{patient['patient_id']}", help="Escalate to CRITICAL"):
                    escalate_patient(patient['patient_id'], 'CRITICAL', "Doctor manually escalated to CRITICAL")
                    st.warning("Patient escalated to CRITICAL!")
                    time.sleep(1)
                    st.rerun()
    
    # Medium Risk Section
    if len(medium_risk) > 0:
        st.markdown("### 🟡 Medium Risk")
        for idx, patient in medium_risk.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 1, 1, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Seen", key=f"seen_{patient['patient_id']}", help="Mark patient as seen"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
            
            with col5:
                if st.button("🔴 Escalate", key=f"escalate_h_{patient['patient_id']}", help="Escalate to HIGH"):
                    escalate_patient(patient['patient_id'], 'HIGH', "Doctor manually escalated to HIGH")
                    st.warning("Patient escalated to HIGH!")
                    time.sleep(1)
                    st.rerun()
            
            with col6:
                if st.button("⬇️ Lower", key=f"lower_m_{patient['patient_id']}", help="Lower to LOW"):
                    escalate_patient(patient['patient_id'], 'LOW', "Doctor manually lowered to LOW")
                    st.info("Risk lowered")
                    time.sleep(1)
                    st.rerun()
    
    # Low Risk Section
    if len(low_risk) > 0:
        st.markdown("### 🟢 Low Risk")
        for idx, patient in low_risk.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Seen", key=f"seen_{patient['patient_id']}", help="Mark patient as seen"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
            
            with col5:
                if st.button("🟡 Escalate", key=f"escalate_l_{patient['patient_id']}", help="Escalate to MEDIUM"):
                    escalate_patient(patient['patient_id'], 'MEDIUM', "Doctor manually escalated to MEDIUM")
                    st.warning("Patient escalated to MEDIUM!")
                    time.sleep(1)
                    st.rerun()


# ============================================================================
# QUEUE STATISTICS
# ============================================================================


st.markdown("---")
st.subheader("📊 Queue Statistics")

queue_state = fetch_queue_state()
analytics = fetch_analytics()

if queue_state:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Patients", queue_state.get('total_patients', 0))
    
    with col2:
        by_risk = queue_state.get('by_risk_level', {})
        st.metric("Critical", by_risk.get('CRITICAL', 0))
    
    with col3:
        st.metric("High Risk", by_risk.get('HIGH', 0))
    
    with col4:
        st.metric("Medium Risk", by_risk.get('MEDIUM', 0))
    
    with col5:
        st.metric("Low Risk", by_risk.get('LOW', 0))
    
    st.metric("Avg Wait Time", f"{queue_state.get('avg_wait_time', 0):.1f} min")

if analytics:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Triages", analytics.get('total_triages', 0))
    
    with col2:
        st.metric("High Risk Rate", f"{analytics.get('high_risk_escalation_rate', 0):.1f}%")
    
    with col3:
        st.metric("Avg Confidence", f"{analytics.get('avg_confidence', 0):.2f}")


# ============================================================================
# AUDIT LOG SECTION
# ============================================================================

st.markdown("---")
with st.expander("📋 **Audit Log** (Click to expand)", expanded=False):
    display_audit_log()


# ============================================================================
# SETTINGS SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    
    st.markdown("### Auto-Escalation Settings")
    
    threshold = st.slider(
        "Auto-escalate threshold (minutes)",
        min_value=5,
        max_value=60,
        value=st.session_state.escalation_threshold_minutes,
        step=5,
        help="Patients waiting longer than this will be auto-escalated"
    )
    
    if threshold != st.session_state.escalation_threshold_minutes:
        st.session_state.escalation_threshold_minutes = threshold
        add_audit_log(
            "SETTINGS_CHANGED",
            details=f"Escalation threshold changed to {threshold} minutes",
            severity="INFO"
        )
    
    st.markdown("### Refresh Interval")
    refresh_interval = st.radio(
        "Auto-refresh interval",
        options=[5, 10, 30],
        format_func=lambda x: f"{x} seconds",
        index=0,
        help="How often to refresh queue data"
    )
    
    st.markdown("### Queue Summary")
    if queue_state:
        st.write(f"**Total Patients:** {queue_state.get('total_patients', 0)}")
        st.write(f"**Last Updated:** {datetime.now().strftime('%H:%M:%S')}")


# ============================================================================
# HEALTH CHECK & CONNECTION STATUS
# ============================================================================


with st.container():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if check_backend_health():
            st.success("✅ Backend Connected")
        else:
            st.error("❌ Backend Disconnected or Initializing")
            st.stop()
    
    with col2:
        st.info(f"🔗 API: {API_BASE_URL}")
    
    with col3:
        st.write(f"🕐 {datetime.now().strftime('%H:%M:%S')}")


st.markdown("---")

# Auto-refresh using time.sleep
time.sleep(5)
st.rerun()
