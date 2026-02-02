"""
EdgeCare: Core Data Models
Pydantic models for patient intake, symptoms, vital signs, triage decisions
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union
from enum import Enum
from datetime import datetime

# ============================================================================
# ENUMS
# ============================================================================

class SymptomSeverity(str, Enum):
    """Clinical severity scale"""
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class RiskLevel(str, Enum):
    """Triage risk classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ============================================================================
# VITAL SIGNS: STANDARDIZED FORMAT
# ============================================================================

class VitalSigns(BaseModel):
    """Standardized vital signs with clinical ranges"""
    heart_rate: Optional[int] = Field(None, ge=0, le=300, description="beats per minute")
    systolic_bp: Optional[int] = Field(None, ge=50, le=300, description="mmHg")
    diastolic_bp: Optional[int] = Field(None, ge=30, le=200, description="mmHg")
    temperature: Optional[float] = Field(None, ge=35.0, le=42.0, description="Celsius")
    oxygen_saturation: Optional[int] = Field(None, ge=70, le=100, description="%")
    
    @validator("diastolic_bp", allow_reuse=True)
    def bp_consistency(cls, v, values):
        """Ensure diastolic < systolic"""
        if "systolic_bp" in values and v and values["systolic_bp"]:
            if v >= values["systolic_bp"]:
                raise ValueError("Diastolic BP must be < Systolic BP")
        return v


# ============================================================================
# SYMPTOM: STANDARDIZED SYMPTOM REPRESENTATION
# ============================================================================

class Symptom(BaseModel):
    """Standardized symptom with severity"""
    name: str = Field(..., description="Symptom name (e.g., 'chest pain')")
    severity: SymptomSeverity = Field(default=SymptomSeverity.MODERATE)
    duration_hours: Optional[float] = Field(None, description="How long symptom has been present")
    notes: Optional[str] = Field(None, description="Additional notes about symptom")


# ============================================================================
# PATIENT INTAKE: INITIAL PATIENT INFORMATION
# ============================================================================

class PatientIntake(BaseModel):
    """Initial patient information captured by nurse"""
    age: Optional[int] = Field(None, ge=0, le=150, description="Patient age in years")
    gender: Optional[str] = Field(None, description="Patient gender")
    chief_complaint: str = Field(..., description="Primary reason for visit")
    symptoms: List[Symptom] = Field(default_factory=list, description="List of reported symptoms")
    vital_signs: Optional[VitalSigns] = Field(None, description="Patient vital signs")
    medical_history: Optional[Union[str, List[str]]] = Field(None, description="Relevant medical history")
    medications: Optional[Union[str, List[str]]] = Field(None, description="Current medications")
    allergies: Optional[Union[str, List[str]]] = Field(None, description="Known allergies")
    
    @validator("medical_history", "medications", "allergies", pre=True)
    def convert_to_string(cls, v):
        """Convert lists to comma-separated strings"""
        if isinstance(v, list):
            return ", ".join(str(item) for item in v)
        return v


# ============================================================================
# TRIAGE DECISION: CLINICAL TRIAGE OUTPUT
# ============================================================================

class TriageDecision(BaseModel):
    """Triage decision from clinical engine"""
    risk_level: RiskLevel = Field(..., description="Assigned risk level")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in decision (0-1)")
    clinical_summary: str = Field(..., description="Why this risk level was assigned")
    suggested_next_steps: str = Field(..., description="Recommended next steps")
    reasoning: Optional[str] = Field(None, description="Detailed reasoning")


# ============================================================================
# TRIAGE ENTRY: COMPLETE PATIENT RECORD IN QUEUE
# ============================================================================

class TriageEntry(BaseModel):
    """Complete entry in the triage queue"""
    patient_id: str = Field(..., description="Unique patient ID (UUID)")
    intake: PatientIntake = Field(..., description="Patient intake information")
    triage_decision: TriageDecision = Field(..., description="Triage decision")
    intake_timestamp: datetime = Field(..., description="When patient was admitted")
    triage_timestamp: datetime = Field(..., description="When triage was completed")
    queue_position: int = Field(default=0, ge=0, description="Position in queue")
    wait_time_minutes: float = Field(default=0.0, ge=0, description="Minutes waiting")
    escalation_reason: Optional[str] = Field(None, description="Why patient was escalated")


# ============================================================================
# QUEUE STATE: SNAPSHOT OF QUEUE STATISTICS
# ============================================================================

class TriageQueueState(BaseModel):
    """Snapshot of queue state"""
    total_patients: int = Field(default=0, ge=0)
    by_risk_level: dict = Field(default_factory=dict, description="Patient count by risk level")
    avg_wait_time: float = Field(default=0.0, ge=0)
    patients: List[TriageEntry] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# QUEUE ANALYTICS: QUALITY METRICS
# ============================================================================

class TriageAnalytics(BaseModel):
    """Queue analytics and quality metrics"""
    total_triages: int = Field(default=0, ge=0)
    distribution_by_risk: dict = Field(default_factory=dict)
    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    median_wait_time: float = Field(default=0.0, ge=0)
    high_risk_escalation_rate: float = Field(default=0.0, ge=0, le=100)