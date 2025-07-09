import os
import json
from datetime import datetime
import random
from db.models import Complaint
from db.db_utils import SessionLocal
from utils.id_generator import generate_complaint_id
from utils.email_service import send_ethics_complaint_email
from langchain_agent.llm_client import query_llm, extract_fields_from_query_llm
from sqlalchemy import or_

# Load officers list
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
with open(os.path.join(DATA_DIR, 'officers_name.json')) as f:
    OFFICERS = json.load(f)

# In-memory conversation state tracker
_conversation_states = {}

def get_conversation_state(user_id):
    return _conversation_states.get(user_id, {'history': []})

def update_conversation_state(user_id, user_message, agent_response):
    state = _conversation_states.setdefault(user_id, {'history': []})
    state['history'].append({
        'role': 'user',
        'message': user_message,
        'timestamp': datetime.utcnow().isoformat()
    })
    state['history'].append({
        'role': 'agent',
        'message': agent_response,
        'timestamp': datetime.utcnow().isoformat()
    })
    return state

# Log a new complaint to the database
def log_complaint(data):
    with SessionLocal() as session:
        complaint = Complaint(**data)
        session.add(complaint)
        session.commit()

# Retrieve all complaints from the database
def get_all_complaints():
    with SessionLocal() as session:
        complaints = session.query(Complaint).all()
        return complaints

# Retrieve a complaint by ID
def get_complaint_by_id(complaint_id):
    with SessionLocal() as session:
        complaint = session.query(Complaint).filter_by(complaint_id=complaint_id).first()
        return complaint

def handle_new_complaint(message, context=None, user_id=None):
    """
    Collects all required fields from the message/context, assigns officer, generates ID, logs to DB, and sends confirmation email.
    Maintains conversation state per user.
    Returns (confirmation_message, updated_context)
    """
    required_fields = [
        'complainant',
        'complainant_email',
        'complaint_type',
        'victim_name',
        'suspect_name',
        'relation',
        'date',
        'details_summary',
        'evidence_provided'
    ]
    if not context:
        context = {
            'collected': {},
            'current_q': 0,
            'confirmed': False
        }
        extracted = extract_all_fields_from_message(message)
        context['collected'] = extracted
        missing = [f for f in required_fields if not extracted.get(f)]
        context['missing'] = missing
        context['current_q'] = 0
        if not missing:
            return _finalize_complaint(extracted, context, user_id)
        else:
            response = f"Thanks for sharing your concern. To help me assist you better, could you please provide a bit more information? For example: {', '.join(missing)}. Just let me know whatever you can, and we'll take it from there!"
            if user_id:
                update_conversation_state(user_id, message, response)
            return (response, context)
    # On every user message, try to extract as many missing fields as possible
    missing = context.get('missing', [])
    collected = context['collected']
    if missing:
        extracted = extract_all_fields_from_message(message)
        for field in missing:
            if extracted.get(field):
                collected[field] = extracted[field]
        new_missing = [f for f in required_fields if not collected.get(f)]
        context['collected'] = collected
        context['missing'] = new_missing
        if not new_missing:
            return _finalize_complaint(collected, context, user_id)
        else:
            response = f"You're doing great! To move forward, could you share a little more about: {', '.join(new_missing)}? Feel free to provide whatever details you have."
            if user_id:
                update_conversation_state(user_id, message, response)
            return (response, context)
    if not context.get('confirmed'):
        response = "Please provide more details about the incident or any missing information."
        if user_id:
            update_conversation_state(user_id, message, response)
        return (response, context)
    else:
        response = "Your complaint has already been submitted. For a new complaint, please refresh the page."
        if user_id:
            update_conversation_state(user_id, message, response)
        return (response, context)

def handle_followup_complaint(message, context=None, user_id=None):
    """
    Continues collecting missing fields for an ongoing complaint registration.
    Returns (response_message, updated_context)
    """
    required_fields = [
        'complainant',
        'complainant_email',
        'complaint_type',
        'victim_name',
        'suspect_name',
        'relation',
        'date',
        'details_summary',
        'evidence_provided'
    ]
    if not context:
        # If no context, treat as new complaint
        return handle_new_complaint(message, context=None, user_id=user_id)
    missing = context.get('missing', [])
    collected = context['collected']
    if missing:
        extracted = extract_all_fields_from_message(message)
        for field in missing:
            if extracted.get(field):
                collected[field] = extracted[field]
        new_missing = [f for f in required_fields if not collected.get(f)]
        context['collected'] = collected
        context['missing'] = new_missing
        if not new_missing:
            return _finalize_complaint(collected, context, user_id)
        else:
            response = f"Thank you! To complete your complaint, could you provide: {', '.join(new_missing)}?"
            if user_id:
                update_conversation_state(user_id, message, response)
            return (response, context)
    if not context.get('confirmed'):
        response = "Please provide more details about the incident or any missing information."
        if user_id:
            update_conversation_state(user_id, message, response)
        return (response, context)
    else:
        response = "Your complaint has already been submitted. For a new complaint, please start again."
        if user_id:
            update_conversation_state(user_id, message, response)
        return (response, context)

import re

def extract_details(message: str) -> str:
    # Simple regex for complaint ID (e.g., ETH-20250703-1914)
    match = re.search(r'ETH-\d{8}-\d{4}', message)
    if match:
        return match.group(0)
    # Else fall back to general keyword-based extraction
    return message.strip()

def summarize_complaint_with_llm(complaint):
    prompt = f"""
    Given the following complaint details, provide a user-friendly summary.

    Complaint ID: {complaint['complaint_id']}
    Type: {complaint['complaint_type']}
    Victim: {complaint['victim_name']}
    Suspect: {complaint['suspect_name']}
    Relation: {complaint['relation']}
    Status: {complaint['status']}
    Officer Assigned: {complaint['assigned_officer']}
    Summary: {complaint['details_summary']}

    Respond in 1-2 lines for a third party.
    """
    return query_llm(prompt)

def get_complaint_details(user_message):
    print(f"[DEBUG] Entered get_complaint_details for: {user_message}")
    """
    Uses LLM to extract all relevant fields/values from the user message, searches the DB for matches, and summarizes the results.
    """
    # 1. Extract fields/values from user query using Gemini
    extracted_fields = extract_fields_from_query_llm(user_message)
    print(f"[DEBUG] LLM extracted_fields: {extracted_fields!r}")

    # Try to parse as JSON dict or list of dicts
    import json
    fields_dict = {}
    # If the list is a list of dicts with 'field' and 'value', convert to a single dict
    if isinstance(extracted_fields, list) and all(isinstance(item, dict) and 'field' in item and 'value' in item for item in extracted_fields):
        fields_dict = {item['field']: item['value'] for item in extracted_fields if item.get('field') and item.get('value')}
    elif isinstance(extracted_fields, dict):
        fields_dict = extracted_fields
    elif isinstance(extracted_fields, list):
        # If it's a list of dicts, merge them
        for item in extracted_fields:
            if isinstance(item, dict):
                fields_dict.update(item)
    else:
        print(f"[DEBUG] LLM output is not a dict or list: {extracted_fields!r}")
        return "No details found in complaints record."

    if not fields_dict:
        print(f"[DEBUG] No valid fields extracted: {extracted_fields!r}")
        return "No details found in complaints record. Try rephrasing."

    all_matches = []
    field_to_matches = {}
    for field, value in fields_dict.items():
        if not field or not value:
            continue
        matches = search_complaints_by_any_field(str(value))
        if matches:
            field_to_matches[(field, value)] = matches
            all_matches.extend(matches)
    # Combine results: intersection if all fields present, else union
    if field_to_matches:
        match_sets = [set(tuple(sorted(m.items())) for m in v) for v in field_to_matches.values()]
        if len(match_sets) > 1:
            intersected = set.intersection(*match_sets)
            matches = [dict(t) for t in intersected] if intersected else []
        else:
            matches = [dict(t) for t in match_sets[0]]
        if not matches:
            matches = [dict(t) for t in set(tuple(sorted(m.items())) for m in all_matches)]
        if not matches:
            return f"Sorry, I couldn't find any complaint records matching your query."
        if len(matches) == 1:
            return summarize_complaint_with_llm(matches[0])
        else:
            summary = "\n".join([
                f"Complaint ID: {c['complaint_id']}, Type: {c['complaint_type']}, Status: {c['status']}, Suspect: {c['suspect_name']}, Victim: {c['victim_name']}, Officer: {c['assigned_officer']}" for c in matches
            ])
            prompt = f"Summarize the following complaint records for the user in a helpful, conversational way:\n{summary}\nRespond in short and for a third party."
            return query_llm(prompt)
    else:
        return "No details found in complaints record. Try rephrasing."
    # Fallback: old logic
    extracted_info = extract_details(user_message)
    matches = search_complaints_by_any_field(extracted_info)
    if not matches:
        return f"Sorry, I couldn't find any complaint records for '{extracted_info}'."
    for c in matches:
        if c['complaint_id'].lower() == extracted_info.lower():
            return summarize_complaint_with_llm(c)
    if len(matches) == 1:
        return summarize_complaint_with_llm(matches[0])
    else:
        summary = "\n".join([
            f"Complaint ID: {c['complaint_id']}, Type: {c['complaint_type']}, Status: {c['status']}, Suspect: {c['suspect_name']}, Victim: {c['victim_name']}, Officer: {c['assigned_officer']}" for c in matches
        ])
        prompt = f"Summarize the following complaint records for the user in a helpful, conversational way:\n{summary}\nRespond in short and for a third party."
        return query_llm(prompt)

def _finalize_complaint(data, context, user_id=None):
    data = data.copy()
    data['status'] = evaluate_complaint_status(data.get('details_summary', ''), data.get('evidence_provided', '')).get('status', 'Pending')
    data['complaint_id'] = generate_complaint_id()
    data['assigned_officer'] = random.choice(OFFICERS)
    data['created_at'] = datetime.utcnow()
    if 'date' in data and isinstance(data['date'], str):
        try:
            data['date'] = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except Exception:
            data['date'] = None
    try:
        log_complaint(data)
        confirmation = f"Thank you. Your complaint has been logged.\n\nComplaint ID: {data['complaint_id']}\nAssigned Officer: {data['assigned_officer']}\n\nYou will receive a confirmation email shortly. Our team will follow up within 5 business days."
        context['confirmed'] = True
        email_data = {
            'Complaint ID': data['complaint_id'],
            'Complaint Type': data.get('complaint_type', ''),
            'Victim Name': data.get('victim_name', ''),
            'Suspect Name': data.get('suspect_name', ''),
            'Relation': data.get('relation', ''),
            'Date': data.get('date', ''),
            'Description': data.get('details_summary', ''),
            'Evidence': data.get('evidence_provided', ''),
            'Assigned To': data.get('assigned_officer', ''),
            'Status': data.get('status', '')
        }
        send_ethics_complaint_email(data.get('complainant_email', ''), data.get('complainant', ''), email_data)
        if user_id:
            update_conversation_state(user_id, data.get('details_summary', ''), confirmation)
        return (confirmation, context)
    except Exception as e:
        response = f"Error logging complaint: {str(e)}"
        if user_id:
            update_conversation_state(user_id, data.get('details_summary', ''), response)
        return (response, context)

def get_complaint_info(complaint_id):
    complaint = get_complaint_by_id(complaint_id)
    if not complaint:
        return None
    return {
        'complaint_id': complaint.complaint_id,
        'date': str(complaint.date),
        'complainant': complaint.complainant,
        'complainant_email': complaint.complainant_email,
        'complaint_type': complaint.complaint_type,
        'victim_name': complaint.victim_name,
        'suspect_name': complaint.suspect_name,
        'relation': complaint.relation,
        'details_summary': complaint.details_summary,
        'evidence_provided': complaint.evidence_provided,
        'status': complaint.status,
        'assigned_officer': complaint.assigned_officer,
        'created_at': str(complaint.created_at)
    }

def extract_all_fields_from_message(message):
    """
    Uses LLM to extract all required complaint fields from a free-text message.
    Returns a dict with keys: complainant, complainant_email, complaint_type, victim_name, suspect_name, relation, date, details_summary, evidence_provided
    """
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'complaint_field_extraction.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    prompt = prompt_template.format(message=message)
    resp = query_llm(prompt)
    raw = resp.strip()
    # Try to parse as JSON
    import json
    try:
        if raw.startswith('```json'):
            raw = raw[len('```json'):].strip()
        if raw.startswith('```'):
            raw = raw[len('```'):].strip()
        if raw.endswith('```'):
            raw = raw[:-3].strip()
        data = json.loads(raw)
    except Exception:
        data = {}
    return data

def evaluate_complaint_status(description: str, evidence: str) -> dict:
    # Load prompt from file
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'status_checker_prompt.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    prompt = prompt_template.format(description=description, evidence=evidence)
    resp = query_llm(prompt)
    text = resp.strip()
    # Parse response
    status = None
    reason = None
    for line in text.split('\n'):
        if line.lower().startswith('status:'):
            status = line.split(':', 1)[1].strip()
        elif line.lower().startswith('reason:'):
            reason = line.split(':', 1)[1].strip()
    return {"status": status or "Needs More Info", "reason": reason or "AI fallback used."}

def search_complaints_by_any_field(query):
    with SessionLocal() as session:
        like_query = f"%{query.lower()}%"
        complaints = session.query(Complaint).filter(
            or_(
                Complaint.complaint_id.ilike(like_query),
                Complaint.complainant.ilike(like_query),
                Complaint.complainant_email.ilike(like_query),
                Complaint.complaint_type.ilike(like_query),
                Complaint.victim_name.ilike(like_query),
                Complaint.suspect_name.ilike(like_query),
                Complaint.relation.ilike(like_query),
                Complaint.details_summary.ilike(like_query),
                Complaint.evidence_provided.ilike(like_query),
                Complaint.status.ilike(like_query),
                Complaint.assigned_officer.ilike(like_query)
            )
        ).all()
        # Return as list of dicts
        return [
            {
                'complaint_id': c.complaint_id,
                'date': str(c.date),
                'complainant': c.complainant,
                'complainant_email': c.complainant_email,
                'complaint_type': c.complaint_type,
                'victim_name': c.victim_name,
                'suspect_name': c.suspect_name,
                'relation': c.relation,
                'details_summary': c.details_summary,
                'evidence_provided': c.evidence_provided,
                'status': c.status,
                'assigned_officer': c.assigned_officer,
                'created_at': str(c.created_at)
            }
            for c in complaints
        ] 