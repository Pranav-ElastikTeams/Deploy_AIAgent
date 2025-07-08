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

GEMINI_API_KEY1 = os.getenv('GEMINI_API_KEY1')
if not GEMINI_API_KEY1:
    raise ValueError("GEMINI_API_KEY1 environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY1)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
with open(os.path.join(DATA_DIR, 'officers_name.json')) as f:
    OFFICERS = json.load(f)

def load_prompt_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'prompt_templates', filename), 'r', encoding='utf-8') as f:
        return f.read()

def extract_all_fields_from_message(message):
    prompt = load_prompt_template('all_fields_extraction_prompt.txt')
    prompt = prompt.format(message=message)
    resp = model.generate_content(prompt)
    raw = resp.text.strip()
    print(f"\n[Gemini Extraction] All Fields Prompt: {prompt}\nRaw Response: {raw}\n")
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

def get_complaint_agent_response(user_message, conversation_state):
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
        extracted = extract_all_fields_from_message(user_message)
        conversation_state['collected'] = extracted
        missing = [f for f in required_fields if not extracted.get(f)]
        conversation_state['missing'] = missing
        conversation_state['current_q'] = 0
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
        if missing:
            return (f"Thanks for sharing your concern. To help me assist you better, could you please provide a bit more information? For example: {', '.join(missing)}. Just let me know whatever you can, and we'll take it from there!", conversation_state)
    # On every user message, try to extract as many missing fields as possible
    missing = conversation_state.get('missing', [])
    collected = conversation_state['collected']
    if missing:
        # Try to extract all missing fields from the user message
        extracted = extract_all_fields_from_message(user_message)
        for field in missing:
            if extracted.get(field):
                collected[field] = extracted[field]
        # Recompute missing fields
        new_missing = [f for f in required_fields if not collected.get(f)]
        conversation_state['collected'] = collected
        conversation_state['missing'] = new_missing
        if not new_missing:
            data = collected.copy()
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
        else:
            return (f"You're doing great! To move forward, could you share a little more about: {', '.join(new_missing)}? Feel free to provide whatever details you have.", conversation_state)
    if not conversation_state.get('confirmed'):
        return ("Please provide more details about the incident or any missing information.", conversation_state)
    else:
        return ("Your complaint has already been submitted. For a new complaint, please refresh the page.", conversation_state) 