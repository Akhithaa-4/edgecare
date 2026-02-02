"""
EdgeCare: Triage Engine using Ollama (Local Inference)
Works offline, no HuggingFace required
"""

import json
import requests
from typing import Dict, Any, Optional
from models import PatientIntake, TriageDecision, RiskLevel

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "alibayram/medgemma"

SYSTEM_PROMPT = """You are EdgeCare, a clinical decision-support triage assistant.

YOUR CONSTRAINTS:
1. You provide DECISION SUPPORT ONLY. You do NOT diagnose or prescribe.
2. You summarize symptoms, assess urgency (LOW/MEDIUM/HIGH/CRITICAL), and suggest next steps.
3. Your output must be valid JSON.

For each triage, output STRICT JSON with:
{
  "clinical_summary": "Brief factual summary of patient presentation",
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "suggested_next_steps": "Recommended next steps for clinical team",
  "confidence_score": 0.85
}

IMPORTANT CLINICAL SAFETY RULES:
- Red-flag symptoms (e.g., chest pain, dyspnea, syncope) must NOT be classified as LOW risk.
- Severity influences confidence, but safety-critical symptoms require escalation.
- When uncertain, prioritize patient safety over specificity.
"""

def apply_clinical_overrides(intake: PatientIntake, decision: TriageDecision) -> TriageDecision:
    """
    Safety-first clinical overrides.
    """

    RED_FLAG_SYMPTOMS = [
        "chest pain",
        "shortness of breath",
        "breathing difficulty",
        "syncope",
        "unconscious",
        "stroke",
        "seizure",
        "severe bleeding"
    ]

    symptom_names = [s.name.lower() for s in intake.symptoms]

    # ---------------------------------------------------------
    # 1️⃣ CRITICAL escalation (OBJECTIVE VITALS)
    # ---------------------------------------------------------
    vitals = intake.vital_signs
    if vitals:
        if (
            (vitals.oxygen_saturation is not None and vitals.oxygen_saturation < 90) or
            (vitals.systolic_bp is not None and vitals.systolic_bp < 90) or
            (vitals.heart_rate is not None and vitals.heart_rate > 130)
        ):
            decision.risk_level = RiskLevel.CRITICAL
            decision.reasoning = (
                (decision.reasoning or "")
                + " | Critical vitals detected (life-threatening)"
            )
            decision.confidence_score = min(1.0, decision.confidence_score + 0.2)
            return decision   # 🚨 STOP further downgrades

    # ---------------------------------------------------------
    # 2️⃣ HIGH escalation for red-flag symptoms
    # ---------------------------------------------------------
    if any(flag in symptom_names for flag in RED_FLAG_SYMPTOMS):
        if decision.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            decision.risk_level = RiskLevel.HIGH
            decision.reasoning = (
                (decision.reasoning or "")
                + " | Safety override: red-flag symptom"
            )

    # ---------------------------------------------------------
    # 3️⃣ Confidence calibration (severity-aware)
    # ---------------------------------------------------------
    severe_present = any(
        s.severity.value in ["SEVERE", "CRITICAL"] for s in intake.symptoms
    )

    if severe_present:
        decision.confidence_score = min(1.0, decision.confidence_score + 0.1)
    else:
        decision.confidence_score = max(0.5, decision.confidence_score - 0.05)

    return decision

class EdgeCareMedGemmaEngine:
    """Ollama-based triage engine (local, offline)"""
    
    def __init__(self):
        self.model = MODEL
        self.url = OLLAMA_URL
        print(f"🔧 EdgeCare Triage Engine (Ollama)")
        print(f"   Model: {MODEL}")
        print(f"   Server: {OLLAMA_URL}")
        print(f"✅ Ready for inference\n")
    
    def _format_intake(self, intake: PatientIntake) -> str:
        """Format patient intake for prompt"""
        
        # Format symptoms
        symptoms_text = ""
        if intake.symptoms:
            symptoms_list = []
            for s in intake.symptoms:
                severity = s.severity.value if hasattr(s.severity, 'value') else str(s.severity)
                duration = f"({s.duration_hours or '?'} hours)" if hasattr(s, 'duration_hours') else ""
                symptoms_list.append(f"   • {s.name} [{severity}] {duration}")
            symptoms_text = "\n".join(symptoms_list)
        else:
            symptoms_text = "   None reported"
        
        # Format vital signs
        vitals_text = "   Not yet obtained"
        if intake.vital_signs:
            vitals = intake.vital_signs
            vitals_text = f"""   • HR: {vitals.heart_rate or '?'} bpm
   • BP: {vitals.systolic_bp or '?'}/{vitals.diastolic_bp or '?'} mmHg
   • Temp: {vitals.temperature or '?'}°C
   • SpO2: {vitals.oxygen_saturation or '?'}%"""
        
        # Format medical history
        history_text = intake.medical_history if intake.medical_history else "None reported"
        meds_text = intake.medications if intake.medications else "None reported"
        allergies_text = intake.allergies if intake.allergies else "None reported"
        
        return f"""PATIENT INTAKE:
Age: {intake.age or '?'} | Gender: {intake.gender or '?'}
Chief Complaint: {intake.chief_complaint}

SYMPTOMS:
{symptoms_text}

VITAL SIGNS:
{vitals_text}

MEDICAL HISTORY:
{history_text}

MEDICATIONS:
{meds_text}

ALLERGIES:
{allergies_text}"""
    
    def _build_prompt(self, intake: PatientIntake) -> str:
        """Construct full prompt"""
        intake_formatted = self._format_intake(intake)
        prompt = f"""{SYSTEM_PROMPT}

{intake_formatted}

TRIAGE ASSESSMENT (output STRICT JSON):"""
        return prompt
    
    def triage(self, intake: PatientIntake) -> TriageDecision:
        """Run triage via Ollama"""
        prompt = self._build_prompt(intake)
        
        try:
            # Call Ollama API
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3
                },
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"⚠️ Ollama error: {response.status_code}. Using fallback.")
                return self._fallback_triage(intake)
            
            response_text = response.json().get("response", "")
            
            # Parse JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                print("⚠️ No JSON found in Ollama response. Using fallback.")
                return self._fallback_triage(intake)
            
            json_text = response_text[json_start:json_end]
            raw_output = json.loads(json_text)
            
        except Exception as e:
            print(f"⚠️ Ollama error: {e}. Using fallback triage.")
            return self._fallback_triage(intake)
        
        # Validate output
        raw_output = self._validate_and_repair_output(raw_output)
        
        # Create decision
        try:
            decision = TriageDecision(
                clinical_summary=raw_output.get("clinical_summary", "Summary unavailable"),
                risk_level=RiskLevel(raw_output.get("risk_level", "MEDIUM")),
                suggested_next_steps=raw_output.get("suggested_next_steps", "Physician evaluation"),
                confidence_score=raw_output.get("confidence_score", 0.75),
                reasoning=raw_output.get("reasoning", "")
            )
            return decision
        except Exception as e:
            print(f"⚠️ Error creating TriageDecision: {e}. Using fallback.")
            return self._fallback_triage(intake)
    
    def _validate_and_repair_output(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate output structure"""
        
        if "clinical_summary" not in raw_output:
            raw_output["clinical_summary"] = "Clinical summary not generated"
        
        if "risk_level" not in raw_output:
            raw_output["risk_level"] = "MEDIUM"
        else:
            level = str(raw_output["risk_level"]).upper().strip()
            if level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                raw_output["risk_level"] = "MEDIUM"
            else:
                raw_output["risk_level"] = level
        
        if "suggested_next_steps" not in raw_output:
            raw_output["suggested_next_steps"] = "Physician evaluation"
        elif isinstance(raw_output["suggested_next_steps"], list):
            raw_output["suggested_next_steps"] = "; ".join(raw_output["suggested_next_steps"])
        
        if "confidence_score" not in raw_output:
            raw_output["confidence_score"] = 0.75
        else:
            try:
                score = float(raw_output["confidence_score"])
                raw_output["confidence_score"] = max(0.0, min(1.0, score))
            except (ValueError, TypeError):
                raw_output["confidence_score"] = 0.75
        
        if "reasoning" not in raw_output:
            raw_output["reasoning"] = ""
        
        return raw_output
    
    def _fallback_triage(self, intake: PatientIntake) -> TriageDecision:
        """Rule-based fallback triage"""
        
        high_risk_keywords = ["chest pain", "dyspnea", "stroke", "unconscious", "bleeding", "severe"]
        chief_complaint_lower = intake.chief_complaint.lower() if intake.chief_complaint else ""
        
        high_risk_count = sum(1 for kw in high_risk_keywords if kw in chief_complaint_lower)
        
        # Check for severe symptoms
        severe_symptoms = any(
            s.severity.value == "SEVERE" or s.severity.value == "CRITICAL" 
            for s in (intake.symptoms or [])
        ) if intake.symptoms else False
        
        if high_risk_count >= 1 or severe_symptoms:
            risk_level = "HIGH"
        elif intake.symptoms and len(intake.symptoms) > 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return TriageDecision(
            clinical_summary=f"{intake.chief_complaint or 'No complaint'} with {len(intake.symptoms or [])} symptom(s)",
            risk_level=RiskLevel(risk_level),
            suggested_next_steps="Physician evaluation",
            confidence_score=0.65,
            reasoning="Fallback triage (Ollama unavailable or failed)"
        )


# Global engine instance
_engine = None


def get_triage_engine() -> EdgeCareMedGemmaEngine:
    """Get or initialize the triage engine"""
    global _engine
    if _engine is None:
        _engine = EdgeCareMedGemmaEngine()
    return _engine


def run_triage(intake: PatientIntake) -> TriageDecision:
    engine = get_triage_engine()

    # Step 1: MedGemma reasoning
    decision = engine.triage(intake)

    # Step 2: Apply safety-aware clinical overrides
    decision = apply_clinical_overrides(intake, decision)

    return decision
