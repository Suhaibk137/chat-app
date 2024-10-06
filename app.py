# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, join_room, emit
import sqlite3
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
import base64
from uuid import uuid4

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')  # Use environment variable
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize SocketIO with threading
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Register adapters and converters for sqlite3
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)

def get_db_connection():
    conn = sqlite3.connect('chat.db', detect_types=sqlite3.PARSE_DECLTYPES)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            message TEXT,
            image TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sender_sid TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Initialize Scheduler for deleting old messages
scheduler = BackgroundScheduler()
scheduler.start()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        room = request.form.get('room')
        if room:
            return redirect(url_for('chat', room=room))
    return render_template('index.html')

@app.route('/chat')
def chat():
    room = request.args.get('room')
    if not room:
        return redirect(url_for('index'))
    return render_template('index.html', room=room)

@socketio.on('join')
def handle_join(data):
    room = data['room']
    join_room(room)
    sender_sid = request.sid  # Unique session ID for the user
    emit('joined', {'sid': sender_sid}, room=sender_sid)  # Send SID back to the user
    emit('status', {'msg': f'A user has entered the room.', 'sid': sender_sid}, room=room)
    # Send existing messages in the room from the last minute
    conn = get_db_connection()
    c = conn.cursor()
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    c.execute("SELECT message, image, timestamp, sender_sid FROM messages WHERE room = ? AND timestamp >= ?", (room, one_minute_ago))
    messages = c.fetchall()
    for msg in messages:
        emit('message', {
            'message': msg[0],
            'image': msg[1],
            'timestamp': msg[2].strftime('%Y-%m-%d %H:%M:%S'),  # Convert datetime to string
            'sender_sid': msg[3]
        })
    conn.close()

@socketio.on('message')
def handle_message(data):
    room = data['room']
    message = data.get('message', '')
    image = data.get('image', '')
    sender_sid = request.sid
    timestamp = datetime.now(timezone.utc)

    image_url = ''
    if image:
        # Decode the Base64 image
        try:
            header, encoded = image.split(',', 1)
            file_ext = header.split('/')[-1].split(';')[0]
            if file_ext not in ALLOWED_EXTENSIONS:
                emit('error', {'msg': 'Invalid image format.'}, room=sender_sid)
                return
            filename = f"{uuid4().hex}.{file_ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            with open(filepath, 'wb') as f:
                f.write(base64.b64decode(encoded))

            image_url = url_for('uploaded_file', filename=filename)
        except Exception as e:
            emit('error', {'msg': 'Failed to process image.'}, room=sender_sid)
            return

    # Save message to the database
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO messages (room, message, image, timestamp, sender_sid) VALUES (?, ?, ?, ?, ?)",
              (room, message, image_url, timestamp, sender_sid))
    conn.commit()
    conn.close()

    emit('message', {
        'message': message,
        'image': image_url,
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'sender_sid': sender_sid
    }, room=room)

def delete_old_messages():
    conn = get_db_connection()
    c = conn.cursor()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
    # Fetch messages older than 1 minute
    c.execute("SELECT id, image FROM messages WHERE timestamp < ?", (cutoff,))
    old_messages = c.fetchall()
    # Delete associated images
    for msg in old_messages:
        image_url = msg[1]
        if image_url:
            # Extract filename from URL
            filename = image_url.split('/')[-1]
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Error deleting image file {filepath}: {e}")
    # Delete messages from the database
    c.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()

# Schedule the deletion of old messages every minute
scheduler.add_job(func=delete_old_messages, trigger="interval", minutes=1)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port)
