import os
from typing import Optional, List
from dotenv import load_dotenv
from langchain_agent.gemini_key_manager import GeminiKeyManager
import time
import json

load_dotenv()

GEMINI_API_KEY3 = os.getenv('GEMINI_API_KEY3')
if not GEMINI_API_KEY3:
    raise ValueError("GEMINI_API_KEY3 environment variable not set.")

gemini_manager = GeminiKeyManager()

def query_llm(prompt: str, history: Optional[List[dict]] = None) -> str:
    print(f"[DEBUG] query_llm called with prompt:\n{prompt}")
    try:
        start = time.time()
        resp = gemini_manager.generate_content(prompt)
        elapsed = time.time() - start
        print(f"[DEBUG] Gemini API call took {elapsed:.2f} seconds")
        print(f"[DEBUG] LLM raw response: {resp.text!r}")
        result = resp.text.strip() if resp and hasattr(resp, 'text') else ''
        if not result:
            print("[DEBUG] LLM returned empty response, using fallback message.")
            return "I'm not sure how to answer that right now. Could you please rephrase or ask something else?"
        return result
    except RuntimeError as e:
        print(f"[DEBUG] {str(e)}")
        raise 

def extract_fields_from_query_llm(user_message: str):
    """
    Uses Gemini LLM to extract all relevant complaint fields and values from a user query.
    Returns a list of dicts: [{"field": ..., "value": ...}, ...]
    """
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_templates', 'entity_field_extraction.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    prompt = prompt_template.format(user_message=user_message)
    print(f"[DEBUG] Entity extraction prompt sent to LLM:\n{prompt}")
    resp = query_llm(prompt)
    raw = resp.strip()
    print(f"[DEBUG] Raw LLM output for entity extraction: {raw!r}")
    try:
        if raw.startswith('```json'):
            raw = raw[len('```json'):].strip()
        if raw.startswith('```'):
            raw = raw[len('```'):].strip()
        if raw.endswith('```'):
            raw = raw[:-3].strip()
        data = json.loads(raw)
        if isinstance(data, dict):
            # Sometimes LLM returns a dict instead of a list
            data = [data]
    except Exception as e:
        print(f"[DEBUG] Failed to parse LLM output as JSON: {e}")
        data = []
    return data 