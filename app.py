from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os
from db.db_utils import init_db, get_db_session
from langchain_agent.supervisor import supervisor_route
from langchain_agent.llm_client import gemini_manager
import json
from db.models import Complaint
import builtins
from flask_socketio import SocketIO, emit
import logging
from logging.config import dictConfig

load_dotenv()

app = Flask(__name__, static_folder='frontend/static', template_folder='frontend/templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize DB
init_db()

DEBUG_LOG = []
MAX_DEBUG_LOG = 200

# Configure logging for production
if not app.debug:
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })

# Security best practices for session cookies
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

@app.route('/')
def index():
    """Render the main chat interface and reset session state."""
    session.pop('conversation_state', None)
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the user and route to the supervisor agent."""
    data = request.get_json()
    user_message = data.get('message', '')
    session_context = session.get('session_context', None)
    try:
        response, new_session_context, agent_type = supervisor_route(user_message, session_context)
        session['session_context'] = new_session_context
        return jsonify({'response': response, 'agent': agent_type})
    except Exception as e:
        logging.exception("Error in /chat endpoint")
        if isinstance(e, RuntimeError) and str(e).startswith('All Gemini API keys exhausted'):
            return jsonify({'response': 'All Gemini API keys are exhausted. Please try again later or contact support.', 'agent': 'error'}), 429
        else:
            return jsonify({'response': f"An error occurred. Please try again later.", 'agent': 'error'}), 500

@app.route('/complaint_types')
def complaint_types():
    """Return the list of complaint types as JSON."""
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    with open(os.path.join(DATA_DIR, 'complaint_types.json')) as f:
        types = json.load(f)
    return jsonify(types)

@app.route('/api/gemini_key_status')
def gemini_key_status():
    """Return the status of Gemini API keys as JSON."""
    status = gemini_manager.get_key_status()
    return jsonify({'status': status})

@app.route('/api/debug_log')
def api_debug_log():
    """Return the debug log (for admin use only)."""
    return jsonify({'log': DEBUG_LOG})

# Function to emit key status update to all clients

def emit_gemini_key_status():
    """Emit Gemini key status update to all connected clients via SocketIO."""
    status = gemini_manager.get_key_status()
    socketio.emit('key_status_update', {'status': status})

gemini_manager.on_status_update = emit_gemini_key_status  # Set the callback after initialization

if __name__ == '__main__':
    # In production, use Gunicorn or another WSGI server. This is for development only.
    socketio.run(app, host='0.0.0.0', port=8000)