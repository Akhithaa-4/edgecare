"""
EdgeCare: Nurse Intake UI (Streamlit)
Patient intake form with symptom assessment, vitals entry, triage submission
"""

import streamlit as st
import requests
import json
from datetime import datetime
from models import PatientIntake, Symptom, VitalSigns, SymptomSeverity

st.set_page_config(
    page_title="EdgeCare - Nurse Triage",
    page_icon="🩺",
    layout="wide"
)

# ============================================================================
# STYLING
# ============================================================================

st.markdown("""
<style>
    .main-title {
        font-size: 2.5em;
        font-weight: bold;
        color: #ffffff;
        margin-bottom: 10px;
    }
    .subtitle {
        font-size: 1.1em;
        color: #666;
        margin-bottom: 20px;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
            
    .info-banner {
        background: rgba(56, 139, 253, 0.15);
        border-left: 4px solid #388BFD;
        color: #C9D1D9;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 10px 0 20px 0;
        font-size: 0.95rem;
    }

    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================

st.markdown('<div class="main-title">🩺 EdgeCare – Nurse Triage Intake</div>', unsafe_allow_html=True)
st.markdown("""
<div class="info-banner">
    🔐 Privacy-preserving, offline-first patient intake
</div>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE
# ============================================================================

if "submitted_patients" not in st.session_state:
    st.session_state.submitted_patients = []
if "form_mode" not in st.session_state:
    st.session_state.form_mode = "entry"

# ============================================================================
# API HELPER
# ============================================================================

BACKEND_URL = "http://localhost:8000"

def submit_to_backend(intake: PatientIntake):
    """Send intake to backend for triage"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/triage",
            json=intake.dict(),
            timeout=180
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Backend error: {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to backend. Ensure backend is running on port 8000."}
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# MAIN FORM
# ============================================================================

with st.form("patient_intake_form"):
    st.markdown("### 👤 Patient Demographics")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        age = st.number_input("Age", min_value=0, max_value=150, value=35)
    
    with col2:
        gender = st.selectbox("Gender", ["M", "F", "O", "Prefer not to say"])
    
    with col3:
        pregnancy = st.selectbox(
            "Pregnancy Status (if applicable)",
            ["N/A", "Not pregnant", "Pregnant", "Unknown"]
        )
    
    # Chief Complaint
    st.markdown("### 🏥 Chief Complaint")
    chief_complaint = st.text_input(
        "Primary reason for visit",
        placeholder="e.g., chest pain, shortness of breath, fever"
    )
    
    # Symptoms
    st.markdown("### 🩹 Symptoms")
    st.write("Add at least one symptom:")
    
    symptoms = []
    symptom_count = st.number_input("Number of symptoms to report", min_value=1, max_value=10, value=1)
    
    for i in range(int(symptom_count)):
        with st.expander(f"Symptom {i+1}"):
            col1, col2 = st.columns(2)
            
            with col1:
                symptom_name = st.text_input(
                    f"Symptom name",
                    key=f"symptom_name_{i}",
                    placeholder="e.g., chest pain, nausea"
                )
                severity = st.selectbox(
                    f"Severity",
                    ["MILD", "MODERATE", "SEVERE"],
                    key=f"symptom_severity_{i}"
                )
            
            with col2:
                onset_minutes = st.number_input(
                    f"Onset (minutes ago)",
                    min_value=0,
                    value=60,
                    key=f"symptom_onset_{i}"
                )
                character = st.text_input(
                    f"Character (sharp, dull, burning, etc.)",
                    key=f"symptom_character_{i}",
                    placeholder="Optional"
                )
            
            if symptom_name:
                symptoms.append(Symptom(
                    name=symptom_name,
                    severity=SymptomSeverity(severity),
                    onset_minutes=int(onset_minutes),
                    character=character or None,
                    associated_symptoms=[],
                    relieving_factors=None,
                    aggravating_factors=None
                ))
    
    # Vitals
    st.markdown("### 📊 Vital Signs (Optional)")
    vitals_provided = st.checkbox("Enter vital signs")
    
    vitals = None
    if vitals_provided:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            hr = st.number_input("Heart Rate (bpm)", min_value=0, max_value=300, value=70)
        with col2:
            systolic = st.number_input("Systolic BP (mmHg)", min_value=50, max_value=300, value=120)
        with col3:
            diastolic = st.number_input("Diastolic BP (mmHg)", min_value=30, max_value=200, value=80)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            rr = st.number_input("Respiratory Rate (breaths/min)", min_value=5, max_value=60, value=16)
        with col2:
            temp = st.number_input("Temperature (°C)", min_value=35.0, max_value=42.0, value=37.0)
        with col3:
            spo2 = st.number_input("SpO2 (%)", min_value=70, max_value=100, value=98)
        
        vitals = VitalSigns(
            heart_rate=int(hr),
            systolic_bp=int(systolic),
            diastolic_bp=int(diastolic),
            respiratory_rate=int(rr),
            temperature=float(temp),
            oxygen_saturation=int(spo2)
        )
    
    # Medical History
    st.markdown("### 📋 Medical History")
    
    history_text = st.text_area(
        "Past medical conditions (comma-separated)",
        placeholder="e.g., Hypertension, Diabetes, Asthma"
    )
    medical_history = [h.strip() for h in history_text.split(",")] if history_text else []
    
    meds_text = st.text_area(
        "Current medications (comma-separated)",
        placeholder="e.g., Metformin, Lisinopril"
    )
    medications = [m.strip() for m in meds_text.split(",")] if meds_text else []
    
    allergies_text = st.text_area(
        "Allergies (comma-separated)",
        placeholder="e.g., Penicillin, Shellfish"
    )
    allergies = [a.strip() for a in allergies_text.split(",")] if allergies_text else []
    
    # ========================================================================
    # SUBMIT
    # ========================================================================
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        submit_btn = st.form_submit_button("📤 Submit for Triage", use_container_width=True)
    
    with col2:
        clear_btn = st.form_submit_button("🔄 Clear Form", use_container_width=True)
    
    with col3:
        st.empty()
    
    # ========================================================================
    # PROCESSING
    # ========================================================================
    
    if submit_btn:
        if not chief_complaint or not symptoms:
            st.error("⚠️ Please provide chief complaint and at least one symptom")
        else:
            with st.spinner("🧠 Running triage through MedGemma..."):
                try:
                    intake = PatientIntake(
                        age=age,
                        gender=gender,
                        chief_complaint=chief_complaint,
                        symptoms=symptoms,
                        medical_history=medical_history,
                        medications=medications,
                        allergies=allergies,
                        vitals=vitals,
                        pregnancy_status=pregnancy if pregnancy != "N/A" else None
                    )
                    
                    result = submit_to_backend(intake)
                    
                    if "error" not in result:
                        st.session_state.submitted_patients.append(result)
                        
                        st.markdown('<div class="success-box">', unsafe_allow_html=True)
                        st.markdown(f"✅ **Triage Submitted Successfully!**")
                        st.markdown(f"**Patient ID:** `{result['patient_id'][:8]}...`")
                        st.markdown(f"**Risk Level:** 🔴 **{result['triage_decision']['risk_level']}**")
                        st.markdown(f"**Confidence:** {result['triage_decision']['confidence_score']:.0%}")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        with st.expander("📋 Full Triage Result"):
                            st.json(result['triage_decision'])
                    else:
                        st.markdown('<div class="error-box">', unsafe_allow_html=True)
                        st.error(f"❌ Error: {result['error']}")
                        st.markdown('</div>', unsafe_allow_html=True)
                
                except Exception as e:
                    st.error(f"❌ Form validation error: {str(e)}")
    
    if clear_btn:
        st.session_state.form_mode = "cleared"

# ============================================================================
# HISTORY
# ============================================================================

if st.session_state.submitted_patients:
    st.markdown("---")
    st.markdown("### 📊 Recent Submissions")
    
    for i, patient in enumerate(st.session_state.submitted_patients[-5:]):
        with st.expander(f"Patient {i+1}: {patient['patient_id'][:8]}... ({patient['triage_decision']['risk_level']})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Risk Level:** {patient['triage_decision']['risk_level']}")
                st.write(f"**Confidence:** {patient['triage_decision']['confidence_score']:.0%}")
                st.write(f"**Summary:** {patient['triage_decision']['clinical_summary']}")
            
            with col2:
                st.write("**Next Steps:**")
                st.write(patient['triage_decision']['suggested_next_steps'])


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
⚠️ **DISCLAIMER:** EdgeCare is a decision-support tool only. It does not replace clinical judgment. 
All triage decisions must be reviewed by a qualified healthcare professional.

🔒 **Privacy:** All data is processed locally. No data is transmitted to external servers.
""")