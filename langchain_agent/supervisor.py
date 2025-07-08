import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_agent.complaint_agent import get_complaint_agent_response
from langchain_agent.inquiry_agent import get_inquiry_agent_response

load_dotenv()

GEMINI_API_KEY2 = os.getenv('GEMINI_API_KEY2')
if not GEMINI_API_KEY2:
    raise ValueError("GEMINI_API_KEY2 environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY2)
llm_model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# LLM prompt for intent classification (now includes delete and update)
INTENT_PROMPT = '''
You are a supervisor AI that routes user messages to the correct agent.
Classify the following user message as one of:
- complaint: If the user is reporting a new ethics complaint, incident, or case.
- inquiry: If the user is asking about the status of a complaint, law, policy, punishment, or general information.
- delete: If the user is asking to delete, remove, erase, or expunge a record, complaint, or person from the system.
- update: If the user is asking to update, modify, change, or edit a record, complaint, or information in the system.

User Message:
"""
{user_message}
"""

Respond with only one word: complaint, inquiry, delete, or update.
'''

# LLM prompt for new complaint detection
NEW_COMPLAINT_PROMPT = '''
You are an AI assistant. Determine if the following user message is an attempt to start a new, separate complaint (not a continuation of a previous one). Only answer 'yes' or 'no'.

User Message:
"""
{user_message}
"""

Is this a new complaint? (yes or no):
'''

def classify_intent(user_message):
    prompt = INTENT_PROMPT.format(user_message=user_message)
    resp = llm_model.generate_content(prompt)
    label = resp.text.strip().lower()
    if 'complaint' in label:
        return 'complaint'
    elif 'inquiry' in label:
        return 'inquiry'
    elif 'delete' in label:
        return 'delete'
    elif 'update' in label:
        return 'update'
    else:
        return 'inquiry'

def is_new_complaint(user_message):
    prompt = NEW_COMPLAINT_PROMPT.format(user_message=user_message)
    resp = llm_model.generate_content(prompt)
    answer = resp.text.strip().lower()
    return answer.startswith('yes')

# session_context: {'complaint': complaint_state, 'inquiry': inquiry_state, 'last_agent': 'complaint' or 'inquiry'}
def supervisor_route(user_message, session_context=None):
    if session_context is None:
        session_context = {'complaint': None, 'inquiry': None, 'last_agent': None}
    # Check if a complaint is in progress and not confirmed
    complaint_state = session_context.get('complaint')
    in_progress_complaint = False
    if complaint_state and isinstance(complaint_state, dict):
        # If 'confirmed' is False or missing, and there are missing fields, it's in progress
        confirmed = complaint_state.get('confirmed', False)
        missing = complaint_state.get('missing', [])
        if not confirmed and (missing or complaint_state.get('collected', {})):
            in_progress_complaint = True
    intent = classify_intent(user_message)
    # If a complaint is in progress, always continue unless user asks to delete/update
    if in_progress_complaint:
        if intent == 'delete':
            response = "Delete requests are not supported in this system. If you need to remove a record, please contact an administrator."
            return response, session_context, 'delete'
        elif intent == 'update':
            response = "Update requests are not supported in this system. If you need to modify a record, please contact an administrator."
            return response, session_context, 'update'
        else:
            # Continue complaint registration
            response, new_state = get_complaint_agent_response(user_message, complaint_state)
            session_context['complaint'] = new_state
            session_context['last_agent'] = 'complaint'
            return response, session_context, 'complaint'
    # Otherwise, normal routing
    if intent == 'complaint':
        if is_new_complaint(user_message):
            session_context['complaint'] = None  # Reset complaint context
        response, new_state = get_complaint_agent_response(user_message, session_context.get('complaint'))
        session_context['complaint'] = new_state
        session_context['last_agent'] = 'complaint'
        return response, session_context, 'complaint'
    elif intent == 'inquiry':
        response, new_state = get_inquiry_agent_response(user_message, session_context.get('inquiry'))
        session_context['inquiry'] = new_state
        session_context['last_agent'] = 'inquiry'
        return response, session_context, 'inquiry'
    elif intent == 'delete':
        response = "Delete requests are not supported in this system. If you need to remove a record, please contact an administrator."
        return response, session_context, 'delete'
    elif intent == 'update':
        response = "Update requests are not supported in this system. If you need to modify a record, please contact an administrator."
        return response, session_context, 'update'
    else:
        response, new_state = get_inquiry_agent_response(user_message, session_context.get('inquiry'))
        session_context['inquiry'] = new_state
        session_context['last_agent'] = 'inquiry'
        return response, session_context, 'inquiry' 