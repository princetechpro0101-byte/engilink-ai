import os, io, json, zipfile, sqlite3
from flask import Flask, render_template, request, jsonify, send_file, Response

app = Flask(__name__)
DB_PATH = "engilink.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS engineers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, specialty TEXT, tags TEXT, location TEXT, experience TEXT, rate TEXT, rating REAL DEFAULT 5.0, bio TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, engineer_id INTEGER, customer_name TEXT, customer_email TEXT, project_details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    if conn.execute("SELECT COUNT(*) FROM engineers").fetchone()[0] == 0:
        conn.executemany("INSERT INTO engineers (name, email, specialty, tags, location, experience, rate, rating, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("Eng. Amina Mwangi", "amina@example.com", "Civil & Structural Engineering", "building,bridge,construction,structural,foundation,concrete,house,road,civil", "Dar es Salaam, Tanzania", "9 Years", "$45/hr", 4.9, "Licensed structural engineer specializing in commercial buildings and residential foundation audits."),
            ("Eng. David Chen", "david@example.com", "AI & Full-Stack Software Engineering", "app,website,software,ai,python,database,api,mobile,cloud,system,code", "Singapore", "7 Years", "$65/hr", 5.0, "Builds scalable web platforms, machine learning pipelines, and custom mobile applications."),
            ("Eng. Sofia Lindqvist", "sofia@example.com", "Renewable Energy & Electrical Engineering", "solar,power,electrical,grid,battery,inverter,circuit,energy,wiring,generator", "Stockholm, Sweden", "11 Years", "$70/hr", 4.8, "Designs off-grid solar microgrids, industrial power systems, and battery storage."),
            ("Eng. Carlos Mendez", "carlos@example.com", "Mechanical & Robotics Engineering", "machine,mechanical,cad,3d,engine,robot,manufacturing,prototype,pump,hvac", "Monterrey, Mexico", "8 Years", "$55/hr", 4.9, "Expert in CAD modeling, industrial machinery troubleshooting, and automated manufacturing.")
        ])
    conn.commit()
    conn.close()

init_db()

def fetch_all_engineers():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM engineers ORDER BY id DESC").fetchall()]
    conn.close()
    return rows

@app.route("/")
def index():
    return render_template("index.html", engineers=fetch_all_engineers())

@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "EngiLink AI", "short_name": "EngiLink", "start_url": "/", "display": "standalone", "background_color": "#0f172a", "theme_color": "#38bdf8", "icons": [{"src": "https://flaticon.com", "sizes": "512x512", "type": "image/png"}]})

@app.route("/sw.js")
def sw():
    return Response("self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));", mimetype="application/javascript")

@app.route("/download-app")
def download_app():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ["app.py", "templates/index.html"]:
            if os.path.exists(f): zf.write(f)
        zf.writestr("requirements.txt", "flask\ngoogle-genai\ngunicorn\n")
    mem.seek(0)
    return send_file(mem, mimetype="application/zip", as_attachment=True, download_name="EngiLink_AI_App.zip")

@app.route("/api/match", methods=["POST"])
def match():
    q = request.get_json().get("query", "").strip()
    engs = fetch_all_engineers()
    if not q: return jsonify({"ai_summary": "Describe your project above.", "matches": engs})
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            roster = [{"id": e["id"], "name": e["name"], "specialty": e["specialty"], "tags": e["tags"]} for e in engs]
            res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Match customer request: '{q}' to engineers: {json.dumps(roster)}. Return JSON with keys summary and matched_ids.")
            parsed = json.loads(res.text.strip().removeprefix("```json").removesuffix("```").strip())
            id_map = {e["id"]: e for e in engs}
            matched = [id_map[i] for i in parsed.get("matched_ids", []) if i in id_map]
            return jsonify({"ai_summary": parsed.get("summary", "Matches:"), "matches": matched or engs[:3]})
        except Exception as e:
            print("Fallback:", e)
    scored = []
    for e in engs:
        s = sum(3 for t in e["tags"].split(",") if t.strip() and t.strip() in q.lower())
        if s > 0: scored.append((s, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored: return jsonify({"ai_summary": f"Top specialists for '{q}':", "matches": engs[:3]})
    return jsonify({"ai_summary": f"Matched {len(scored)} specialist(s) in <strong>{scored[0][1]['specialty']}</strong>.", "matches": [x[1] for x in scored]})

@app.route("/api/register", methods=["POST"])
def register():
    d = request.get_json()
    req = ["name", "email", "specialty", "tags", "location", "experience", "rate", "bio"]
    if not all(d.get(k, "").strip() for k in req): return jsonify({"error": "Fill all fields."}), 400
    conn = get_db()
    conn.execute("INSERT INTO engineers (name, email, specialty, tags, location, experience, rate, bio) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [d[k].strip() for k in req])
    conn.commit()
    conn.close()
    return jsonify({"message": "Profile published globally!"})

@app.route("/api/book", methods=["POST"])
def book():
    d = request.get_json()
    if not all([d.get("engineer_id"), d.get("customer_name"), d.get("customer_email"), d.get("project_details")]): return jsonify({"error": "Fill all fields."}), 400
    conn = get_db()
    conn.execute("INSERT INTO bookings (engineer_id, customer_name, customer_email, project_details) VALUES (?, ?, ?, ?)", (d["engineer_id"], d["customer_name"], d["customer_email"], d["project_details"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "Consultation request sent!"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
