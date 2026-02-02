"""
Quick test to verify MedGemma is working with EdgeCare
Run this AFTER updating triage_engine.py with MODEL = "alibayram/medgemma"

Usage:
    python test_medgemma.py
"""

from models import PatientIntake, Symptom, VitalSigns, SymptomSeverity
from triage_engine import run_triage

print("\n" + "="*70)
print("🏥 EdgeCare MedGemma Test Suite")
print("="*70 + "\n")

# Test Case 1: High-Risk Patient (Cardiac Emergency)
print("TEST 1: HIGH-RISK CARDIAC PATIENT")
print("-" * 70)

patient_cardiac = PatientIntake(
    age=58,
    gender="M",
    chief_complaint="Severe chest pain radiating to left arm",
    symptoms=[
        Symptom(name="Chest pain", severity=SymptomSeverity.SEVERE, duration_hours=1.5),
        Symptom(name="Shortness of breath", severity=SymptomSeverity.MODERATE, duration_hours=1.5),
        Symptom(name="Diaphoresis", severity=SymptomSeverity.MODERATE, duration_hours=1.5)
    ],
    vital_signs=VitalSigns(
        heart_rate=115,
        systolic_bp=165,
        diastolic_bp=105,
        temperature=37.1,
        oxygen_saturation=93
    ),
    medical_history="Hypertension, Type 2 Diabetes, Previous MI (2020)",
    medications="Aspirin 81mg daily, Metoprolol 50mg BID, Atorvastatin",
    allergies="NKDA"
)

try:
    print("Submitting to MedGemma for triage...\n")
    decision1 = run_triage(patient_cardiac)
    
    print(f"✅ Risk Level: {decision1.risk_level.value}")
    print(f"📊 Confidence: {decision1.confidence_score:.2%}")
    print(f"📝 Summary: {decision1.clinical_summary}")
    print(f"🔧 Next Steps: {decision1.suggested_next_steps}")
    
    if decision1.risk_level.value in ["CRITICAL", "HIGH"]:
        print("\n✅ TEST 1 PASSED: High-risk patient correctly identified!\n")
    else:
        print("\n⚠️ TEST 1 WARNING: Expected CRITICAL/HIGH, got", decision1.risk_level.value, "\n")
        
except Exception as e:
    print(f"❌ TEST 1 FAILED: {e}\n")

# Test Case 2: Low-Risk Patient
print("="*70)
print("TEST 2: LOW-RISK PATIENT")
print("-" * 70)

patient_lowrisk = PatientIntake(
    age=32,
    gender="F",
    chief_complaint="Mild headache and fatigue",
    symptoms=[
        Symptom(name="Headache", severity=SymptomSeverity.MILD, duration_hours=4),
        Symptom(name="Fatigue", severity=SymptomSeverity.MILD, duration_hours=2)
    ],
    vital_signs=VitalSigns(
        heart_rate=78,
        systolic_bp=118,
        diastolic_bp=76,
        temperature=36.9,
        oxygen_saturation=98
    ),
    medical_history="No significant medical history",
    medications="Multivitamin daily",
    allergies="NKDA"
)

try:
    print("Submitting to MedGemma for triage...\n")
    decision2 = run_triage(patient_lowrisk)
    
    print(f"✅ Risk Level: {decision2.risk_level.value}")
    print(f"📊 Confidence: {decision2.confidence_score:.2%}")
    print(f"📝 Summary: {decision2.clinical_summary}")
    print(f"🔧 Next Steps: {decision2.suggested_next_steps}")
    
    if decision2.risk_level.value in ["LOW", "MEDIUM"]:
        print("\n✅ TEST 2 PASSED: Low-risk patient correctly identified!\n")
    else:
        print("\n⚠️ TEST 2 WARNING: Expected LOW/MEDIUM, got", decision2.risk_level.value, "\n")
        
except Exception as e:
    print(f"❌ TEST 2 FAILED: {e}\n")

# Test Case 3: Medium-Risk Patient
print("="*70)
print("TEST 3: MEDIUM-RISK PATIENT")
print("-" * 70)

patient_mediumrisk = PatientIntake(
    age=67,
    gender="M",
    chief_complaint="Acute lower back pain with some leg weakness",
    symptoms=[
        Symptom(name="Lower back pain", severity=SymptomSeverity.SEVERE, duration_hours=6),
        Symptom(name="Leg weakness", severity=SymptomSeverity.MODERATE, duration_hours=6),
        Symptom(name="Numbness in feet", severity=SymptomSeverity.MODERATE, duration_hours=6)
    ],
    vital_signs=VitalSigns(
        heart_rate=88,
        systolic_bp=145,
        diastolic_bp=88,
        temperature=37.0,
        oxygen_saturation=97
    ),
    medical_history="Chronic back pain, Arthritis, Hypertension",
    medications="Lisinopril, Ibuprofen as needed",
    allergies="NKDA"
)

try:
    print("Submitting to MedGemma for triage...\n")
    decision3 = run_triage(patient_mediumrisk)
    
    print(f"✅ Risk Level: {decision3.risk_level.value}")
    print(f"📊 Confidence: {decision3.confidence_score:.2%}")
    print(f"📝 Summary: {decision3.clinical_summary}")
    print(f"🔧 Next Steps: {decision3.suggested_next_steps}")
    
    if decision3.risk_level.value in ["MEDIUM", "HIGH"]:
        print("\n✅ TEST 3 PASSED: Medium-risk patient correctly identified!\n")
    else:
        print("\n⚠️ TEST 3 WARNING: Expected MEDIUM/HIGH, got", decision3.risk_level.value, "\n")
        
except Exception as e:
    print(f"❌ TEST 3 FAILED: {e}\n")

# Summary
print("="*70)
print("🏥 TEST SUITE COMPLETED")
print("="*70)
print("\nIf all tests passed, MedGemma is working correctly!")
print("You can now run your full EdgeCare system with medical-grade AI.")
print("\nNext steps:")
print("1. Fix the 10 syntax errors in priority_queue.py and backend.py")
print("2. Start Ollama: ollama serve")
print("3. Run: python backend.py")
print("4. Run: streamlit run ui_nurse.py")
print("5. Run: streamlit run ui_doctor.py")
print("\n" + "="*70 + "\n")
