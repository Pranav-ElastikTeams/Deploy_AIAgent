import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from langchain_agent.db_agent import get_complaint_info, search_complaints_by_any_field
from langchain_agent.llm_client import query_llm

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

load_dotenv()

PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'law_policy_answer.txt')

COMPLAINT_ID_PATTERN = r'ETH-\d{8}-\d{4}'

def load_prompt_template():
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def extract_complaint_id(user_message):
    match = re.search(COMPLAINT_ID_PATTERN, user_message)
    if match:
        return match.group(0)
    return None

def handle_policy_query(user_message, user_id=None, complaint_id=None):
    print(f"[DEBUG] handle_policy_query called with user_message: {user_message}, user_id: {user_id}, complaint_id: {complaint_id}")
    # Detect complaint ID in user message if not provided
    if not complaint_id:
        complaint_id = extract_complaint_id(user_message)
    print(f"[DEBUG] Extracted complaint_id: {complaint_id}")
    complaint_details = None
    complaint_type = None
    if complaint_id:
        complaint_details = get_complaint_info(complaint_id)
        print(f"[DEBUG] complaint_details: {complaint_details}")
        complaints_data = [complaint_details] if complaint_details else []
        if complaint_details:
            complaint_type = complaint_details.get('complaint_type', None)
    else:
        # Search all fields for relevant complaints
        complaints_data = search_complaints_by_any_field(user_message)
        print(f"[DEBUG] complaints_data from search: {complaints_data}")
        if complaints_data and len(complaints_data) == 1:
            complaint_type = complaints_data[0].get('complaint_type', None)
    complaints_json = json.dumps(complaints_data, ensure_ascii=False)
    print(f"[DEBUG] complaints_json: {complaints_json}")
    # Prepare conversation history
    if user_id:
        conversation_state = get_conversation_state(user_id)
        history = conversation_state['history']
    else:
        history = []
    history_text = ""
    for turn in history:
        if turn.get('role') == 'user':
            history_text += f"User: {turn.get('message','')}\n"
        elif turn.get('role') == 'agent':
            history_text += f"Agent: {turn.get('message','')}\n"
    print(f"[DEBUG] history_text: {history_text}")
    # Build prompt, include complaint type if available
    prompt_template = load_prompt_template()
    prompt = prompt_template.format(
        complaints_data=complaints_json,
        user_question=user_message,
        conversation_history=history_text
    )
    if complaint_type:
        prompt += f"\n\nThe complaint type for {complaint_id} is: {complaint_type}. Please answer the user's question using the relevant law or policy for this type."
    print(f"[DEBUG] Final prompt sent to LLM:\n{prompt}")
    try:
        resp_text = query_llm(prompt)
    except Exception as e:
        raise
    print(f"[DEBUG] LLM response: {resp_text}")
    agent_response = resp_text
    # Update conversation state
    if user_id:
        update_conversation_state(user_id, user_message, agent_response)
    return agent_response, (get_conversation_state(user_id) if user_id else {'history': history}) 