import google.generativeai as genai
import os

def load_prompt_template(filename):
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompt_templates', filename), 'r', encoding='utf-8') as f:
        return f.read()

def evaluate_complaint_status(description: str, evidence: str) -> dict:
    # Rules-based logic can be re-enabled if needed. Currently, only Gemini-based logic is used.
    prompt_template = load_prompt_template('status_checker_prompt.txt')
    prompt = prompt_template.format(description=description, evidence=evidence)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    resp = model.generate_content(prompt)
    text = resp.text.strip()
    # Parse Gemini response
    status = None
    reason = None
    for line in text.split('\n'):
        if line.lower().startswith('status:'):
            status = line.split(':', 1)[1].strip()
        elif line.lower().startswith('reason:'):
            reason = line.split(':', 1)[1].strip()
    return {"status": status or "Needs More Info", "reason": reason or "AI fallback used."}
