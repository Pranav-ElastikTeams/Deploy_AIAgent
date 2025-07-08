from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os
from db.db_utils import init_db, get_db_session
from langchain_agent.supervisor import supervisor_route
import json
from db.models import Complaint

load_dotenv()

app = Flask(__name__, static_folder='frontend/static', template_folder='frontend/templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key')  # Add a secret key for session

# Initialize DB
init_db()

@app.route('/')
def index():
    session.pop('conversation_state', None)
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    # Get or initialize session_context
    session_context = session.get('session_context', None)
    response, new_session_context, agent_type = supervisor_route(user_message, session_context)
    session['session_context'] = new_session_context
    return jsonify({'response': response, 'agent': agent_type})

@app.route('/complaint_types')
def complaint_types():
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    with open(os.path.join(DATA_DIR, 'complaint_types.json')) as f:
        types = json.load(f)
    return jsonify(types)

@app.route('/inquiry')
def inquiry():
    return render_template('inquiry.html')

if __name__ == '__main__':
    app.run(debug=True) 

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8000)