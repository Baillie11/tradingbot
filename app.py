from flask import Flask
from flask_socketio import SocketIO
from routes import create_app
import logging

# Initialize the Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

if __name__ == '__main__':
    create_app(socketio, app)
