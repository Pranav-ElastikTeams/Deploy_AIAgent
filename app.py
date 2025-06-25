from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os
from db.db_utils import init_db
from langchain_agent.agent import get_agent_response
import json

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
    user_message = request.json.get('message')
    # Retrieve or initialize conversation state from session
    conversation_state = session.get('conversation_state', {})
    response, updated_state = get_agent_response(user_message, conversation_state)
    # Update session with new state
    session['conversation_state'] = updated_state
    return jsonify({'response': response})

@app.route('/complaint_types')
def complaint_types():
    DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    with open(os.path.join(DATA_DIR, 'complaint_types.json')) as f:
        types = json.load(f)
    return jsonify(types)

# if __name__ == '__main__':
#     app.run(debug=True) 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)