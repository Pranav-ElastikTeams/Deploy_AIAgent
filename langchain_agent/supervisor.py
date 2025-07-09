import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_agent.db_agent import log_complaint, get_all_complaints, handle_new_complaint, handle_followup_complaint, get_complaint_details, search_complaints_by_any_field
from langchain_agent.policy_agent import handle_policy_query
from langchain_agent.llm_client import query_llm, extract_fields_from_query_llm
import re

load_dotenv()

GEMINI_API_KEY1 = os.getenv('GEMINI_API_KEY1')
if not GEMINI_API_KEY1:
    raise ValueError("GEMINI_API_KEY1 environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY1)
llm_model = genai.GenerativeModel(model_name="gemini-1.5-flash")

def load_prompt_template(filename):
    with open(os.path.join(os.path.dirname(__file__), 'prompt_templates', filename), 'r', encoding='utf-8') as f:
        return f.read()

def classify_intent(user_message, session_context=None):
    print(f"[DEBUG] classify_intent called with user_message: {user_message}")
    prompt = load_prompt_template('intent_classification.txt').format(message=user_message)
    print(f"[DEBUG] Intent classification prompt: {prompt}")
    label = query_llm(prompt)
    print(f"[DEBUG] Intent classification LLM label: {label!r}")
    if not label or not isinstance(label, str):
        print("[DEBUG] LLM returned empty or non-string label, defaulting to 'user_friendly'")
        return 'user_friendly'
    match = re.search(r"intent\s*[:\-]?\s*([\w_]+)", label, re.IGNORECASE)
    if match:
        intent_raw = match.group(1).strip().lower()
    else:
        intent_raw = label.strip().lower().replace('**','').replace('*','')
        if 'intent:' in intent_raw:
            intent_raw = intent_raw.split('intent:')[-1].strip()
    print(f"[DEBUG] Extracted intent_raw: {intent_raw!r}")
    valid_intents = [
        'new_complaint', 'follow_up_complaint', 'law_policy_query', 'complaint_details', 'user_friendly'
    ]
    if intent_raw in valid_intents:
        return intent_raw
    print("[DEBUG] Intent not recognized, defaulting to 'user_friendly'")
    return 'user_friendly'

def is_new_complaint(user_message):
    print(f"[DEBUG] is_new_complaint called with user_message: {user_message}")
    prompt = load_prompt_template('new_complaint_detection.txt').format(user_message=user_message)
    answer = query_llm(prompt)
    print(f"[DEBUG] is_new_complaint LLM answer: {answer}")
    answer = answer.strip().lower()
    return answer.startswith('yes')

def is_entity_query(user_message):
    # Patterns for entity/person queries
    patterns = [
        r'^who is [\w\s]+\??$',
        r'^do you know [\w\s]+\??$',
        r'^is there any record for [\w\s]+\??$',
        r'^what do [\w\s]+ do\??$',
        r'^how [\w\s]+',
    ]
    user_message_lower = user_message.strip().lower()
    for pat in patterns:
        if re.match(pat, user_message_lower):
            return True
    return False

def extract_entity_from_message(user_message):
    # Try to extract the entity/person from common question patterns
    import re
    patterns = [
        r'^who is ([\w\s]+)\??$',
        r'^do you know ([\w\s]+)\??$',
        r'^is there any record for ([\w\s]+)\??$',
        r'^what do ([\w\s]+) do\??$',
        r'^how ([\w\s]+)',
    ]
    user_message_lower = user_message.strip().lower()
    for pat in patterns:
        m = re.match(pat, user_message_lower)
        if m:
            entity = m.group(1).strip(' ?')
            # Capitalize each word for better DB match
            entity = ' '.join([w.capitalize() for w in entity.split()])
            return entity
    return user_message  # fallback to full message

# session_context: {'complaint': complaint_state, 'inquiry': inquiry_state, 'last_agent': 'complaint' or 'inquiry'}
def supervisor_route(user_message, session_context=None):
    print(f"[DEBUG] supervisor_route called with user_message: {user_message}, session_context: {session_context}")
    if session_context is None:
        session_context = {'complaint': None, 'inquiry': None, 'last_agent': None}

    # 1. Intent classification
    if is_entity_query(user_message):
        print(f"[DEBUG] Detected entity/person query pattern.")
        intent = 'complaint_details'
    else:
        intent = classify_intent(user_message, session_context)
    print(f"[DEBUG] supervisor_route detected intent: {intent}")

    # 2.1 New Complaint
    if intent == 'new_complaint':
        # 2.2.1: If there is an incomplete complaint context, force user to finish it first
        if session_context.get('complaint') and not session_context['complaint'].get('confirmed', False):
            response = "You have an incomplete complaint registration. Please complete it before starting a new one."
            session_context['last_agent'] = 'complaint'
            return response, session_context, 'complaint'
        # Start a new complaint registration (reset context)
        session_context['complaint'] = None
        response, updated_context = handle_new_complaint(user_message, context=None)
        session_context['complaint'] = updated_context
        session_context['last_agent'] = 'complaint'
        return response, session_context, 'complaint'

    # 2.2 Follow Up Complaint
    elif intent == 'follow_up_complaint':
        complaint_ctx = session_context.get('complaint')
        if not complaint_ctx:
            # No complaint in context, treat as new complaint
            response, updated_context = handle_new_complaint(user_message, context=None)
        else:
            response, updated_context = handle_followup_complaint(user_message, context=complaint_ctx)
        session_context['complaint'] = updated_context
        session_context['last_agent'] = 'complaint'
        return response, session_context, 'complaint'

    # 2.3 Complaint Details
    elif intent == 'complaint_details':
        # Extract DB fields from input and match with table attributes
        response = get_complaint_details(user_message)
        session_context['last_agent'] = 'inquiry'
        return response, session_context, 'inquiry'

    # 2.4 Law/Policy Query
    elif intent == 'law_policy_query':
        # Try to extract DB fields from input using the shared entity extraction logic
        extracted_fields = extract_fields_from_query_llm(user_message)
        # Convert to dict if needed
        fields_dict = {}
        if isinstance(extracted_fields, list) and all(isinstance(item, dict) and 'field' in item and 'value' in item for item in extracted_fields):
            fields_dict = {item['field']: item['value'] for item in extracted_fields if item.get('field') and item.get('value')}
        elif isinstance(extracted_fields, dict):
            fields_dict = extracted_fields
        # If we got any DB field, try to find a matching complaint record
        complaint_record = None
        if fields_dict:
            # Try to find a matching complaint (use the first non-empty match)
            for value in fields_dict.values():
                matches = search_complaints_by_any_field(str(value))
                if matches:
                    complaint_record = matches[0]
                    break
        # 2.4.1 If got DB field, pass record + question to policy agent
        if complaint_record:
            response, _ = handle_policy_query(user_message, complaint_id=complaint_record.get('complaint_id'))
        # 2.4.2 If not, pass only question to policy agent
        else:
            response, _ = handle_policy_query(user_message)
        session_context['last_agent'] = 'inquiry'
        return response, session_context, 'inquiry'

    # 2.5 User Friendly (chitchat, greeting, etc.)
    elif intent == 'user_friendly':
        # Use policy agent for a general response (as in 2.4.2)
        response, _ = handle_policy_query(user_message)
        session_context['last_agent'] = 'user_friendly'
        return response, session_context, 'user_friendly'

    # Fallback
    else:
        response = "I'm sorry, I didn't understand your request. Could you please rephrase or specify if you want to file a complaint, ask about a policy, or check complaint details?"
        session_context['last_agent'] = 'unknown'
        return response, session_context, 'unknown' 