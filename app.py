import os
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'engilink-super-secret-key-2026')

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB max upload

DB_NAME = 'engilink.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Users table (Real Sign Up & Login for Engineers and Customers)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            account_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Verified Engineer Profiles
    conn.execute('''
        CREATE TABLE IF NOT EXISTS engineers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT NOT NULL,
            experience INTEGER NOT NULL,
            rate INTEGER NOT NULL,
            skills TEXT NOT NULL,
            linkedin_url TEXT,
            avatar_url TEXT,
            contact TEXT NOT NULL,
            verified INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Customer Problem Clips
    conn.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            clip_path TEXT,
            budget INTEGER DEFAULT 0,
            contact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', 'All').strip()

    conn = get_db()

    # Build dynamic SQL query for Amazon-style Search & Category Filter
    sql = 'SELECT * FROM engineers WHERE 1=1'
    params = []

    if category_filter and category_filter != 'All':
        sql += ' AND role = ?'
        params.append(category_filter)

    if search_query:
        sql += ' AND (name LIKE ? OR skills LIKE ? OR location LIKE ? OR role LIKE ?)'
        like_term = f'%{search_query}%'
        params.extend([like_term, like_term, like_term, like_term])

    sql += ' ORDER BY id DESC'
    engineers = conn.execute(sql, params).fetchall()
    problems = conn.execute('SELECT * FROM problems ORDER BY id DESC').fetchall()
    conn.close()

    return render_template(
        'index.html',
        engineers=engineers,
        problems=problems,
        search_query=search_query,
        category_filter=category_filter,
        user_name=session.get('user_name'),
        account_type=session.get('account_type')
    )

@app.route('/signup', methods=['POST'])
def signup():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    account_type = request.form.get('account_type', 'customer')

    if full_name and email and password:
        conn = get_db()
        try:
            pw_hash = generate_password_hash(password)
            cur = conn.execute(
                'INSERT INTO users (full_name, email, password_hash, account_type) VALUES (?, ?, ?, ?)',
                (full_name, email, pw_hash, account_type)
            )
            conn.commit()
            session['user_id'] = cur.lastrowid
            session['user_name'] = full_name
            session['user_email'] = email
            session['account_type'] = account_type
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        session['user_email'] = user['email']
        session['account_type'] = user['account_type']

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register-engineer', methods=['POST'])
def register_engineer():
    name = request.form.get('name', '').strip()
    role = request.form.get('role', '').strip()
    location = request.form.get('location', '').strip()
    experience = request.form.get('experience', 1)
    rate = request.form.get('rate', 50)
    skills = request.form.get('skills', '').strip()
    linkedin_url = request.form.get('linkedin_url', '').strip()
    contact = request.form.get('contact', '').strip()

    # Handle optional profile photo upload
    avatar_url = None
    photo = request.files.get('avatar')
    if photo and photo.filename != '':
        filename = secure_filename(photo.filename)
        unique_name = f"avatar_{int(time.time())}_{filename}"
        saved_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        photo.save(saved_path)
        avatar_url = f"/static/uploads/{unique_name}"

    if name and role and contact:
        conn = get_db()
        conn.execute(
            '''INSERT INTO engineers 
               (user_id, name, role, location, experience, rate, skills, linkedin_url, avatar_url, contact) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (session.get('user_id'), name, role, location, experience, rate, skills, linkedin_url, avatar_url, contact)
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
    budget = request.form.get('budget', 0)
    contact = request.form.get('contact', '').strip()

    clip_path = None
    file = request.files.get('clip')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        unique_name = f"clip_{int(time.time())}_{filename}"
        saved_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(saved_path)
        clip_path = f"/static/uploads/{unique_name}"

    if customer_name and title and contact:
        conn = get_db()
        conn.execute(
            '''INSERT INTO problems 
              (customer_name, category, title, description, clip_path, budget, contact) 
              VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (customer_name, category, title, description, clip_path, budget, contact)
        )
        conn.commit()
        conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
