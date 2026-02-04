"""
EdgeCare: Advanced Priority Queue with Fairness & Audit Trail
Implements clinical triage fairness: urgency + waiting time
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from models import TriageEntry, RiskLevel, TriageQueueState, TriageAnalytics
import statistics
SEVERITY_SCORE = {
    "MILD": 1,
    "MODERATE": 2,
    "SEVERE": 3,
    "CRITICAL": 4
}

def get_patient_severity_score(entry: TriageEntry) -> int:
    """
    Highest severity among patient's symptoms.
    """
    if not entry.intake.symptoms:
        return 0

    return max(
        SEVERITY_SCORE.get(s.severity.value, 0)
        for s in entry.intake.symptoms
    )
RISK_PRIORITY_WEIGHT = {
    RiskLevel.CRITICAL: 100,
    RiskLevel.HIGH: 75,
    RiskLevel.MEDIUM: 50,
    RiskLevel.LOW: 25
}


class FairTriageQueue:
    """
    Clinical queue respecting:
    1. Clinical urgency (HIGH always before LOW)
    2. Waiting time fairness (within same risk level, FIFO)
    3. Escalation rules (deteriorating patients)
    4. Audit trail (full history)
    """
    
    def __init__(self):
        self.queue: List[TriageEntry] = []
        self.audit_log: List[Dict] = []
        self.creation_time = datetime.now()
    
    def add_patient(self, entry: TriageEntry) -> None:
        """Add new patient to queue"""
        entry.queue_position = len(self.queue) + 1
        entry.wait_time_minutes = 0.0
        self.queue.append(entry)
        
        self._log_action(
            action="PATIENT_ADDED",
            patient_id=entry.patient_id,
            risk_level=entry.triage_decision.risk_level.value,
            position=entry.queue_position
        )
    
    def get_sorted_queue(self) -> List[TriageEntry]:
        """
        Return queue sorted by priority + fairness.
        Priority = urgency + waiting time
        """
        for entry in self.queue:
            entry.wait_time_minutes = (
                datetime.now() - entry.intake_timestamp
            ).total_seconds() / 60.0
        
        sorted_queue = sorted(
            self.queue,
            key=lambda e: (
                -RISK_PRIORITY_WEIGHT[e.triage_decision.risk_level],  # 1️⃣ Risk
                -get_patient_severity_score(e),                       # 2️⃣ Severity
                -e.triage_decision.confidence_score,                  # 3️⃣ Confidence
                e.intake_timestamp                                    # 4️⃣ Fairness
            )
        )

        
        for i, entry in enumerate(sorted_queue, 1):
            entry.queue_position = i
        
        return sorted_queue
    
    def escalate_patient(self, patient_id: str, new_risk_level: RiskLevel, 
                        reason: str) -> Optional[TriageEntry]:
        """
        Re-triage patient to higher urgency.
        Common scenario: Patient deteriorates while waiting
        """
        for entry in self.queue:
            if entry.patient_id == patient_id:
                old_level = entry.triage_decision.risk_level
                entry.triage_decision.risk_level = new_risk_level
                entry.escalation_reason = reason
                
                self._log_action(
                    action="ESCALATION",
                    patient_id=patient_id,
                    old_risk=old_level.value,
                    new_risk=new_risk_level.value,
                    reason=reason
                )
                
                return entry
        return None
    
    def mark_seen(self, patient_id: str) -> Optional[TriageEntry]:
        """Move patient from queue (assigned to physician)"""
        for i, entry in enumerate(self.queue):
            if entry.patient_id == patient_id:
                removed = self.queue.pop(i)
                
                self._log_action(
                    action="PATIENT_SEEN",
                    patient_id=patient_id,
                    wait_time_minutes=removed.wait_time_minutes,
                    risk_level=removed.triage_decision.risk_level.value
                )
                
                return removed
        return None
    
    def get_queue_state(self) -> TriageQueueState:
        """Get complete queue snapshot"""
        sorted_queue = self.get_sorted_queue()
        
        distribution = {level.value: 0 for level in RiskLevel}
        for entry in sorted_queue:
            distribution[entry.triage_decision.risk_level.value] += 1
        
        wait_times = [e.wait_time_minutes for e in sorted_queue]
        avg_wait = statistics.mean(wait_times) if wait_times else 0.0
        
        return TriageQueueState(
            total_patients=len(sorted_queue),
            by_risk_level=distribution,
            avg_wait_time=avg_wait,
            patients=sorted_queue,
            timestamp=datetime.now()
        )
    
    def get_analytics(self) -> TriageAnalytics:
        """Generate quality metrics"""
        state = self.get_queue_state()
        
        high_critical = state.by_risk_level.get("HIGH", 0) + state.by_risk_level.get("CRITICAL", 0)
        high_risk_rate = (high_critical / state.total_patients * 100) if state.total_patients > 0 else 0

        
        confidences = [e.triage_decision.confidence_score for e in self.queue 
                      if hasattr(e, 'triage_decision')]
        avg_confidence = statistics.mean(confidences) if confidences else 0.75
        
        total_patients = state.total_patients
        high_critical = (
            state.by_risk_level.get("HIGH", 0) +
            state.by_risk_level.get("CRITICAL", 0)
        )

        high_risk_rate = (
            (high_critical / total_patients) * 100
            if total_patients > 0 else 0
        )

        return TriageAnalytics(
            total_triages=total_patients,  # ✅ patients, not audit log
            distribution_by_risk=state.by_risk_level,
            avg_confidence=avg_confidence,
            median_wait_time=statistics.median(
                [e.wait_time_minutes for e in self.queue]
            ) if self.queue else 0,
            high_risk_escalation_rate=high_risk_rate
        )

    
    def _log_action(self, action: str, **details) -> None:
        """Internal audit logging"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            **details
        }
        self.audit_log.append(log_entry)
    
    def export_audit_log(self) -> List[Dict]:
        """Export full audit trail for compliance"""
        return self.audit_log.copy()
    
    def health_check(self) -> Dict:
        """Monitor queue health"""
        state = self.get_queue_state()
        alerts = []
        
        critical_count = state.by_risk_level.get("CRITICAL", 0)
        if critical_count > 0:
            alerts.append(f"⚠️ {critical_count} CRITICAL patient(s) waiting")
        
        high_risk_patients = [e for e in self.queue if e.triage_decision.risk_level == RiskLevel.HIGH]
        long_wait_threshold = 15
        for patient in high_risk_patients:
            if patient.wait_time_minutes > long_wait_threshold:
                alerts.append(f"⚠️ HIGH risk patient {patient.patient_id[:8]}... waiting {patient.wait_time_minutes:.1f} min")
        
        return {
            "queue_size": state.total_patients,
            "distribution": state.by_risk_level,
            "avg_wait": state.avg_wait_time,
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }


_queue = None

def get_queue() -> FairTriageQueue:
    """Get or initialize the triage queue"""
    global _queue
    if _queue is None:
        _queue = FairTriageQueue()
    return _queue