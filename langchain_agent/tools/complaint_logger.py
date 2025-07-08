from db.models import Complaint
from db.db_utils import get_db_session, SessionLocal

def log_complaint(data):
    with SessionLocal() as session:
        complaint = Complaint(**data)
        session.add(complaint)
        session.commit()

# Complaint fields: complaint_id, date, complainant, complainant_email, complaint_type, victim_name, suspect_name, relation, details_summary, evidence_provided, status, assigned_officer, created_at 