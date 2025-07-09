import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

load_dotenv()

GEMINI_API_KEYS = [
    os.getenv('GEMINI_API_KEY1'),
    os.getenv('GEMINI_API_KEY2'),
    os.getenv('GEMINI_API_KEY3'),
]

class GeminiKeyManager:
    def __init__(self, model_name="gemini-1.5-flash"):
        self.keys = [k for k in GEMINI_API_KEYS if k]
        self.model_name = model_name
        self.current_index = 0
        self.exhausted = [False] * len(self.keys)
        self.api_call_counts = [0] * len(self.keys)
        self.on_status_update = None  # Callback for status updates
        if not self.keys:
            raise ValueError("No Gemini API keys found in environment.")
        self._set_model()

    def _set_model(self):
        genai.configure(api_key=self.keys[self.current_index])
        self.model = genai.GenerativeModel(model_name=self.model_name)

    def _switch_key(self):
        self.exhausted[self.current_index] = True
        if self.on_status_update:
            self.on_status_update()  # Emit update when a key is exhausted
        for i, exhausted in enumerate(self.exhausted):
            if not exhausted:
                self.current_index = i
                self._set_model()
                return True
        return False  # All keys exhausted

    def generate_content(self, prompt, **kwargs):
        last_exception = None
        for _ in range(len(self.keys)):
            try:
                self.api_call_counts[self.current_index] += 1
                print(f"[DEBUG] Gemini API (key {self.current_index+1}) called {self.api_call_counts[self.current_index]} times. Using key: {self.keys[self.current_index][:8]}...")
                return self.model.generate_content(prompt, **kwargs)
            except ResourceExhausted as e:
                print(f"[DEBUG] Gemini API key {self.current_index+1} exhausted: {self.keys[self.current_index][:8]}...")
                last_exception = e
                if not self._switch_key():
                    break
        if self.on_status_update:
            self.on_status_update()  # Emit update if all keys are exhausted
        raise RuntimeError("All Gemini API keys exhausted.") from last_exception

    def get_current_key_name(self):
        return f"GEMINI_API_KEY{self.current_index+1}"

    def get_current_key_value(self):
        return self.keys[self.current_index]

    def get_key_status(self):
        return [not exhausted for exhausted in self.exhausted] 