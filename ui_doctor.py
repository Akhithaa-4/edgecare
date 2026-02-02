"""
EdgeCare Doctor Dashboard UI - Streamlit
Real-time queue visualization, priority display, patient actions

FIXED VERSION: Proper backend connection with LONGER timeout
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://127.0.0.1:8000"  # Use 127.0.0.1 on Windows
REQUEST_TIMEOUT = 60  # INCREASED: Was 5, now 30 seconds (backend needs time for Ollama)

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
</style>
""", unsafe_allow_html=True)

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
    """Fetch patient queue from backend"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/queue",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
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
        return None
    except requests.exceptions.Timeout:
        st.error(f"❌ Backend timeout (>{REQUEST_TIMEOUT}s). Backend might be initializing.")
        st.info("If you see Ollama initialization messages in backend terminal, this is normal. Try again in a few seconds.")
        return None
    except Exception as e:
        st.error(f"❌ Error fetching queue: {str(e)}")
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
            json={"new_risk_level": new_risk_level, "reason": reason},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error escalating patient: {str(e)}")
        return None


def mark_patient_seen(patient_id):
    """Mark patient as seen"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/queue/mark-seen/{patient_id}",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error marking patient as seen: {str(e)}")
        return None


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

if len(df) == 0:
    st.info("📊 No patients in queue")
else:
    # Organize by risk level
    st.subheader("📋 Patient Queue (Priority Order)")
    
    high_risk = df[df['risk_level'] == 'HIGH']
    medium_risk = df[df['risk_level'] == 'MEDIUM']
    low_risk = df[df['risk_level'] == 'LOW']
    
    # High Risk Section
    if len(high_risk) > 0:
        st.markdown("### 🔴 High Risk (Immediate Attention)")
        for idx, patient in high_risk.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Mark Seen", key=f"seen_{patient['patient_id']}"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
    
    # Medium Risk Section
    if len(medium_risk) > 0:
        st.markdown("### 🟡 Medium Risk")
        for idx, patient in medium_risk.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Mark Seen", key=f"seen_{patient['patient_id']}"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
                    time.sleep(1)
                    st.rerun()
    
    # Low Risk Section
    if len(low_risk) > 0:
        st.markdown("### 🟢 Low Risk")
        for idx, patient in low_risk.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            
            with col1:
                st.write(f"**{patient['chief_complaint']}**")
                st.caption(f"ID: {patient['patient_id'][:8]}...")
            
            with col2:
                st.write(f"Age: {patient['age']} | Gender: {patient['gender']}")
                st.caption(f"Symptoms: {patient['symptoms_count']}")
            
            with col3:
                st.metric("Confidence", f"{patient['confidence_score']:.1%}")
            
            with col4:
                if st.button("✅ Mark Seen", key=f"seen_{patient['patient_id']}"):
                    mark_patient_seen(patient['patient_id'])
                    st.success("Patient marked as seen!")
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
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Patients", queue_state.get('total_patients', 0))
    
    with col2:
        by_risk = queue_state.get('by_risk_level', {})
        st.metric("High Risk", by_risk.get('HIGH', 0))
    
    with col3:
        st.metric("Medium Risk", by_risk.get('MEDIUM', 0))
    
    with col4:
        st.metric("Low Risk", by_risk.get('LOW', 0))
    
    st.metric("Avg Wait Time", f"{queue_state.get('avg_wait_time', 0):.1f} min")

if analytics:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Triages", analytics.get('total_triages', 0))
    
    with col2:
        st.metric("High Risk Rate", f"{analytics.get('high_risk_escalation_rate', 0):.1%}")
    
    with col3:
        st.metric("Avg Confidence", f"{analytics.get('avg_confidence', 0):.2f}")

# ============================================================================
# AUTO-REFRESH LOOP
# ============================================================================
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
time.sleep(5)
st.rerun()