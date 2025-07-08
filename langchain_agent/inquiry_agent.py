import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
from langchain_agent.tools.status_checker import evaluate_complaint_status
from db.db_utils import get_db_session, SessionLocal
from db.models import Complaint
from sqlalchemy.orm import Session

load_dotenv()

GEMINI_API_KEY2 = os.getenv('GEMINI_API_KEY2')
if not GEMINI_API_KEY2:
    raise ValueError("GEMINI_API_KEY2 environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY2)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def load_prompt_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'prompt_templates', filename), 'r', encoding='utf-8') as f:
        return f.read()

def get_inquiry_agent_response(user_message, conversation_state=None):
    # Always fetch latest complaints data from the database
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
    if conversation_state and 'history' in conversation_state:
        for turn in conversation_state['history']:
            if turn.get('role') == 'user':
                history_text += f"User: {turn.get('message','')}\n"
            elif turn.get('role') == 'agent':
                history_text += f"Agent: {turn.get('message','')}\n"
    prompt_template = load_prompt_template('inquiry_workflow_prompt.txt')
    prompt = prompt_template.format(complaints_data=complaints_json, user_question=user_message, conversation_history=history_text)
    print('\n--- Gemini INPUT PROMPT ---\n', prompt, '\n--------------------------\n')
    resp = model.generate_content(prompt)
    print('\n--- Gemini OUTPUT RESPONSE ---\n', resp.text.strip(), '\n-----------------------------\n')
    # Store context for follow-up
    if conversation_state is None:
        conversation_state = {'history': []}
    conversation_state['history'].append({'role': 'user', 'message': user_message})
    conversation_state['history'].append({'role': 'agent', 'message': resp.text.strip()})
    return resp.text.strip(), conversation_state 