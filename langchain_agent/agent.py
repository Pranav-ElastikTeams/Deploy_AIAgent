import os
import json
from dotenv import load_dotenv
from .tools.complaint_logger import log_complaint
from utils.id_generator import generate_complaint_id
import google.generativeai as genai
from datetime import datetime
import random
from langchain_agent.tools.status_checker import evaluate_complaint_status
from utils.email_service import send_ethics_complaint_email

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# Load officers list only (other data is not used in this file)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
with open(os.path.join(DATA_DIR, 'officers_name.json')) as f:
    OFFICERS = json.load(f)

def load_prompt_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'prompt_templates', filename), 'r', encoding='utf-8') as f:
        return f.read()

def extract_field_value(question, answer, field):
    prompt_template = load_prompt_template('field_extraction_prompt.txt')
    prompt = prompt_template.format(question=question, answer=answer, field=field)
    resp = model.generate_content(prompt)
    print(f"\n[Gemini Extraction] Field: {field}, Prompt: {prompt}\nResponse: {resp.text.strip()}\n\n")
    value = resp.text.strip()
    if value.lower() == 'null':
        return None
    return value

def extract_all_fields_from_message(message):
    prompt = load_prompt_template('all_fields_extraction_prompt.txt')
    prompt = prompt.format(message=message)
    resp = model.generate_content(prompt)
    raw = resp.text.strip()
    print(f"\n[Gemini Extraction] All Fields Prompt: {prompt}\nRaw Response: {raw}\n")
    # Remove code block markers if present
    if raw.startswith('```json'):
        raw = raw[len('```json'):].strip()
    if raw.startswith('```'):
        raw = raw[len('```'):].strip()
    if raw.endswith('```'):
        raw = raw[:-3].strip()
    print(f"[Gemini Extraction] Cleaned JSON: {raw}\n")
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"[Gemini Extraction] JSON decode error: {e}")
        data = {}
    return data

# Main agent function with improved flow
# Now extracts all fields from the first message, then asks for missing fields
# Only asks for missing info, otherwise logs complaint

def get_agent_response(user_message, conversation_state):
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
    if not conversation_state:
        conversation_state = {
            'collected': {},
            'current_q': 0,
            'confirmed': False
        }
        # Extract all fields from the first message
        extracted = extract_all_fields_from_message(user_message)
        conversation_state['collected'] = extracted
        # Find missing fields
        missing = [f for f in required_fields if not extracted.get(f)]
        conversation_state['missing'] = missing
        conversation_state['current_q'] = 0
        # If NO missing fields, log immediately
        if not missing:
            data = extracted.copy()
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
                conversation_state['confirmed'] = True
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
                return (confirmation, conversation_state)
            except Exception as e:
                return (f"Error logging complaint: {str(e)}", conversation_state)
        # If missing fields, ask for the first one
        if missing:
            next_field = missing[0]
            return (f"Please provide the following information: {next_field.replace('_', ' ')}.", conversation_state)
    # If still missing fields, ask for them one by one
    missing = conversation_state.get('missing', [])
    current_q = conversation_state.get('current_q', 0)
    collected = conversation_state['collected']
    if missing and current_q < len(missing):
        field = missing[current_q]
        value = user_message.strip()
        if field == 'date':
            try:
                date_obj = datetime.strptime(value, '%Y-%m-%d').date()
                value = str(date_obj)
            except Exception:
                return (f"Please provide a valid date (YYYY-MM-DD) for the incident.", conversation_state)
        if field == 'complainant_email':
            value = value.lower()
        collected[field] = value
        conversation_state['collected'] = collected
        conversation_state['current_q'] += 1
        current_q += 1
        if current_q < len(missing):
            next_field = missing[current_q]
            return (f"Please provide the following information: {next_field.replace('_', ' ')}.", conversation_state)
    # After all fields are collected, log the complaint
    if not conversation_state.get('confirmed'):
        data = collected.copy()
        status_result = evaluate_complaint_status(data.get('details_summary', ''), data.get('evidence_provided', ''))
        print(f"[Status Checker] Status: {status_result['status']}, Reason: {status_result['reason']}")
        data['status'] = status_result['status']
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
            conversation_state['confirmed'] = True
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
            return (confirmation, conversation_state)
        except Exception as e:
            return (f"Error logging complaint: {str(e)}", conversation_state)
    else:
        return ("Your complaint has already been submitted. For a new complaint, please refresh the page.", conversation_state)

def get_inquiry_response(user_message, history=None):
    # Always fetch latest complaints data from the database
    from db.db_utils import SessionLocal
    from db.models import Complaint
    with SessionLocal() as session:
        complaints = session.query(Complaint).all()
    def serialize(complaint):
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
    complaints_data = [serialize(c) for c in complaints]
    import json as _json
    complaints_json = _json.dumps(complaints_data, ensure_ascii=False)
    # Format conversation history
    history_text = ""
    if history:
        for turn in history:
            if turn.get('role') == 'user':
                history_text += f"User: {turn.get('message','')}\n"
            elif turn.get('role') == 'agent':
                history_text += f"Agent: {turn.get('message','')}\n"
    prompt_template = load_prompt_template('inquiry_workflow_prompt.txt')
    prompt = prompt_template.format(complaints_data=complaints_json, user_question=user_message, conversation_history=history_text)
    print('\n--- Gemini INPUT PROMPT ---\n', prompt, '\n--------------------------\n')
    resp = model.generate_content(prompt)
    print('\n--- Gemini OUTPUT RESPONSE ---\n', resp.text.strip(), '\n-----------------------------\n')
    return resp.text.strip()
