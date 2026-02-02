"""
EdgeCare: FastAPI Backend - ULTRA SIMPLE VERSION
Fixed HTTP timeout issues
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from datetime import datetime
import logging

from models import PatientIntake, TriageEntry, RiskLevel
from triage_engine import run_triage
from priority_queue import get_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EdgeCare API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# SERIALIZATION HELPER
# ============================================================================

def serialize_patient(entry: TriageEntry) -> dict:
    """Serialize patient to JSON"""
    try:
        risk = entry.triage_decision.risk_level.value
        conf = float(entry.triage_decision.confidence_score)
        summary = str(entry.triage_decision.clinical_summary)
        age = entry.intake.age or "N/A"
        gender = entry.intake.gender or "N/A"
        complaint = entry.intake.chief_complaint or "N/A"
        symptoms_count = len(entry.intake.symptoms) if entry.intake.symptoms else 0
        
        return {
            "patient_id": str(entry.patient_id),
            "queue_position": int(entry.queue_position),
            "age": age,
            "gender": gender,
            "chief_complaint": complaint,
            "symptoms_count": symptoms_count,
            "risk_level": risk,
            "confidence_score": conf,
            "clinical_summary": summary,
            "wait_time_minutes": float(entry.wait_time_minutes or 0),
            "intake_timestamp": entry.intake_timestamp.isoformat(),
            "triage_timestamp": entry.triage_timestamp.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error serializing patient: {e}")
        return {"error": str(e), "patient_id": str(entry.patient_id)}

# ============================================================================
# ROUTES
# ============================================================================

@app.on_event("startup")
async def startup():
    logger.info("🚀 EdgeCare API Starting")

@app.post("/triage")
async def submit_triage(intake: PatientIntake):
    """Submit patient for triage"""
    try:
        patient_id = str(uuid4())
        intake_time = datetime.now()
        
        logger.info(f"📋 Triage: {patient_id[:8]}... - {intake.chief_complaint}")
        
        triage_decision = run_triage(intake)
        triage_time = datetime.now()
        
        entry = TriageEntry(
            patient_id=patient_id,
            intake=intake,
            triage_decision=triage_decision,
            intake_timestamp=intake_time,
            triage_timestamp=triage_time,
            queue_position=0,
            wait_time_minutes=0.0
        )
        
        queue = get_queue()
        queue.add_patient(entry)
        
        logger.info(f"✅ Patient queued: {triage_decision.risk_level.value}")
        return entry
        
    except Exception as e:
        logger.error(f"❌ Triage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue")
async def get_queue_endpoint():
    """Get current queue"""
    try:
        queue = get_queue()
        patients = queue.get_sorted_queue()
        
        result = [serialize_patient(p) for p in patients]
        logger.info(f"📊 Queue: {len(result)} patients")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Queue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/state")
async def get_state():
    """Get queue state"""
    try:
        queue = get_queue()
        state = queue.get_queue_state()
        
        return {
            "total_patients": state.total_patients,
            "by_risk_level": state.by_risk_level,
            "avg_wait_time": round(state.avg_wait_time, 1),
        }
        
    except Exception as e:
        logger.error(f"❌ State error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/analytics")
async def get_analytics_endpoint():
    """Get analytics"""
    try:
        queue = get_queue()
        analytics = queue.get_analytics()
        
        return {
            "total_triages": analytics.total_triages,
            "high_risk_escalation_rate": round(analytics.high_risk_escalation_rate, 1),
            "avg_confidence": round(analytics.avg_confidence, 2),
        }
        
    except Exception as e:
        logger.error(f"❌ Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/escalate/{patient_id}")
async def escalate(patient_id: str, new_risk_level: str, reason: str = ""):
    """Escalate patient"""
    try:
        queue = get_queue()
        entry = queue.escalate_patient(patient_id, RiskLevel(new_risk_level), reason)
        
        if entry:
            return serialize_patient(entry)
        else:
            raise HTTPException(status_code=404, detail="Patient not found")
            
    except Exception as e:
        logger.error(f"❌ Escalate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/mark-seen/{patient_id}")
async def mark_seen(patient_id: str):
    """Mark patient as seen"""
    try:
        queue = get_queue()
        entry = queue.mark_seen(patient_id)
        
        if entry:
            return serialize_patient(entry)
        else:
            raise HTTPException(status_code=404, detail="Patient not found")
            
    except Exception as e:
        logger.error(f"❌ Mark-seen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/health")
async def health():
    """Health check"""
    try:
        queue = get_queue()
        health_data = queue.health_check()
        return health_data
    except Exception as e:
        logger.error(f"❌ Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audit-log")
async def audit_log():
    """Get audit log"""
    try:
        queue = get_queue()
        return queue.export_audit_log()
    except Exception as e:
        logger.error(f"❌ Audit log error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def api_health():
    """API health"""
    return {"status": "healthy"}

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)