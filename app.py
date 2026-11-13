import os
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure Upload Folder for Customer Problem Clips
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB max upload size

DB_NAME = 'engilink.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Table for Real Registered Engineers
    conn.execute('''
        CREATE TABLE IF NOT EXISTS engineers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT NOT NULL,
            experience INTEGER NOT NULL,
            rate INTEGER NOT NULL,
            skills TEXT NOT NULL,
            contact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Table for Customer Engineering Problems & Clips
    conn.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            clip_path TEXT,
            contact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database tables on startup
init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    engineers = conn.execute('SELECT * FROM engineers ORDER BY id DESC').fetchall()
    problems = conn.execute('SELECT * FROM problems ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', engineers=engineers, problems=problems)

@app.route('/register-engineer', methods=['POST'])
def register_engineer():
    name = request.form.get('name', '').strip()
    role = request.form.get('role', '').strip()
    location = request.form.get('location', '').strip()
    experience = request.form.get('experience', 1)
    rate = request.form.get('rate', 50)
    skills = request.form.get('skills', '').strip()
    contact = request.form.get('contact', '').strip()

    if name and role and contact:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO engineers (name, role, location, experience, rate, skills, contact) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, role, location, experience, rate, skills, contact)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('index'))

@app.route('/submit-problem', methods=['POST'])
def submit_problem():
    customer_name = request.form.get('customer_name', '').strip()
    category = request.form.get('category', '').strip()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    contact = request.form.get('contact', '').strip()

    clip_path = None
    file = request.files.get('clip')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        unique_name = f"{int(time.time())}_{filename}"
        saved_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(saved_path)
        clip_path = f"/static/uploads/{unique_name}"

    if customer_name and title and contact:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO problems (customer_name, category, title, description, clip_path, contact) VALUES (?, ?, ?, ?, ?, ?)',
            (customer_name, category, title, description, clip_path, contact)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
