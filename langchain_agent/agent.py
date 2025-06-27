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

# Main agent function with improved flow
def get_agent_response(user_message, conversation_state):
    # If no state, expect the first user message to be the complaint type
    if not conversation_state:
        conversation_state = {
            'collected': {},
            'questions': [],
            'current_q': 0,
            'confirmed': False
        }
        # Save the complaint type from the first user message
        complaint_type = user_message.strip()
        conversation_state['collected']['complaint_type'] = complaint_type
        prompt_template = load_prompt_template('complaint_questions_prompt.txt')
        prompt = prompt_template.format(complaint_type=complaint_type)
        resp = model.generate_content(prompt)
        print(f"\n[Gemini Extraction] Prompt: {prompt}\nResponse: {resp.text.strip()}\n")
        questions = [q.lstrip('*- ').strip() for q in resp.text.strip().split('\n') if q.strip()]
        conversation_state['questions'] = questions
        conversation_state['current_q'] = 0
        # Ask the first question
        return (questions[0], conversation_state)

    # If in the middle of asking questions
    questions = conversation_state.get('questions', [])
    current_q = conversation_state.get('current_q', 0)
    collected = conversation_state['collected']

    # Map the order of fields to collect
    field_order = [
        'complainant',
        'complainant_email',
        'subject',
        'staff_role',
        'date',
        'details_summary',
        'evidence_provided'
    ]
    if 0 <= current_q < len(field_order):
        field = field_order[current_q]
        question = questions[current_q]
        # Use Gemini to extract the value for each field
        if field == 'details_summary':
            collected[field] = user_message.strip()
        else:
            extracted = extract_field_value(question, user_message, field)
            if not extracted:
                return (question, conversation_state)
            # For date, validate format and ensure not in the future
            if field == 'date':
                try:
                    date_obj = datetime.strptime(extracted, '%Y-%m-%d').date()
                    if date_obj > datetime.utcnow().date():
                        return (question, conversation_state)
                except Exception:
                    return (question, conversation_state)
            # For email, convert to lowercase
            if field == 'complainant_email' and extracted:
                extracted = extracted.lower()
            collected[field] = extracted
        conversation_state['collected'] = collected
        conversation_state['current_q'] += 1
        current_q += 1
        if current_q < len(questions):
            return (questions[current_q], conversation_state)

    # After all questions, log the complaint
    if not conversation_state.get('confirmed'):
        data = collected.copy()
        # Evaluate status using status_checker
        status_result = evaluate_complaint_status(data.get('details_summary', ''), data.get('evidence_provided', ''))
        print(f"[Status Checker] Status: {status_result['status']}, Reason: {status_result['reason']}")
        data['status'] = status_result['status']
        data['complaint_id'] = generate_complaint_id()
        data['assigned_officer'] = random.choice(OFFICERS)
        data['created_at'] = datetime.utcnow()

        # Convert date string to datetime.date object
        if 'date' in data and isinstance(data['date'], str):
            try:
                data['date'] = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except Exception:
                data['date'] = None
        try:
            log_complaint(data)
            summary = "\n".join([f"{k}: {v}" for k, v in data.items() if k not in ['created_at', 'assigned_officer']])
            confirmation = f"Thank you. Your complaint has been logged.\n\nComplaint ID: {data['complaint_id']}\nAssigned Officer: {data['assigned_officer']}\n\nYou will receive a confirmation email shortly. Our team will follow up within 5 business days."
            conversation_state['confirmed'] = True
            # Prepare email data
            email_data = {
                'Complaint ID': data['complaint_id'],
                'Complaint Type': data.get('complaint_type', ''),
                'Subject': data.get('subject', ''),
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
    from db.db_utils import get_db_session
    from db.models import Complaint
    session = get_db_session()
    complaints = session.query(Complaint).all()
    session.close()
    def serialize(complaint):
        return {
            'complaint_id': complaint.complaint_id,
            'date': str(complaint.date),
            'complainant': complaint.complainant,
            'complainant_email': complaint.complainant_email,
            'complaint_type': complaint.complaint_type,
            'subject': complaint.subject,
            'details_summary': complaint.details_summary,
            'evidence_provided': complaint.evidence_provided,
            'status': complaint.status,
            'assigned_officer': complaint.assigned_officer,
            'staff_role': complaint.staff_role,
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
