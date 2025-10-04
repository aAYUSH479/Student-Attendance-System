from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import sqlite3, qrcode, io, json, pandas as pd, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"
DB = "attendance.db"
EXCEL_FILE = "attendance.xlsx"

# ----------- Initialize DB -------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Student table
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  roll_no TEXT UNIQUE,
                  name TEXT,
                  password TEXT)''')

    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  roll_no TEXT,
                  name TEXT,
                  date TEXT,
                  time TEXT)''')

    # Admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT)''')

    # Predefined students
    predefined_students = [
        ("101", "Ayush Singh"),
        ("102", "Rohan Kumar"),
        ("103", "Priya Sharma"),
        ("104", "Ankit Verma"),
        ("105", "Neha Gupta"),
        ("106", "Vikas Yadav"),
        ("107", "Simran Kaur"),
        ("108", "Rahul Sharma"),
        ("109", "Sneha Patel"),
        ("110", "Arjun Mehta")
    ]


    for roll, name in predefined_students:
        password = name[:4].upper() + "123"
        c.execute("SELECT * FROM students WHERE roll_no=?", (roll,))
        if not c.fetchone():
            c.execute("INSERT INTO students (roll_no, name, password) VALUES (?, ?, ?)",
                      (roll, name, password))

    # Predefined admins
    predefined_admins = [
        ("admin1", "admin123"),
        ("admin2", "admin456")
    ]
    for username, password in predefined_admins:
        c.execute("SELECT * FROM admins WHERE username=?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", (username, password))

    conn.commit()
    conn.close()

# ----------- Helper: export to excel -------------
def export_to_excel():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM attendance", conn)
    conn.close()
    if not df.empty:
        df.to_excel(EXCEL_FILE, index=False)
    else:
        # create empty file with headers
        df = pd.DataFrame(columns=["id","roll_no","name","date","time"])
        df.to_excel(EXCEL_FILE, index=False)

# ----------- Routes -------------

@app.route("/")
def home():
    return render_template("index.html")

# Student Login
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        name = request.form["name"].strip()
        password = request.form["password"].strip()

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE name=? AND password=?", (name, password))
        student = c.fetchone()
        conn.close()

        if student:
            session["student"] = {"id": student[0], "roll_no": student[1], "name": student[2]}
            return redirect(url_for("student_dashboard"))
        else:
            return render_template("login.html", error="Invalid student credentials!")
    return render_template("login.html")

# Admin Login
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
        admin = c.fetchone()
        conn.close()

        if admin:
            session["admin"] = {"id": admin[0], "username": admin[1]}
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Invalid admin credentials!")
    return render_template("admin_login.html")

# Student Dashboard
@app.route("/student")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("login"))
    return render_template("student.html", student=session["student"])

# Generate Student QR
@app.route("/student_qr")
def student_qr():
    if "student" not in session:
        return redirect(url_for("login"))
    
    student = session["student"]
    data = {"roll_no": student["roll_no"], "name": student["name"]}

    # Ensure static/qr folder exists
    qr_folder = os.path.join(app.root_path, 'static', 'qr')
    os.makedirs(qr_folder, exist_ok=True)

    # File path for student QR
    qr_filename = f"{student['roll_no']}.png"
    qr_path = os.path.join(qr_folder, qr_filename)

    # Generate and save QR image
    img = qrcode.make(json.dumps(data))
    img.save(qr_path)

    # Return HTML template (not send_file)
    return render_template("student.html", student=student, qr_file=url_for('static', filename='qr/' + qr_filename))

# Admin Dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance ORDER BY id DESC")
    records = c.fetchall()
    conn.close()
    return render_template("admin.html", records=records, admin=session["admin"])

# Mark Attendance
@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    if "admin" not in session:
        return jsonify({"status":"error","message":"not authorized"}), 401

    try:
        if request.is_json:
            payload = request.get_json()
            qr_data = payload.get("qr_data")
        else:
            qr_data = request.form.get("qr_data") or request.values.get("qr_data")
        student = json.loads(qr_data)
        roll_no = student.get("roll_no")
        name = student.get("name")
    except Exception as e:
        return jsonify({"status":"error","message":"invalid qr data"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    c.execute("INSERT INTO attendance (roll_no, name, date, time) VALUES (?,?,?,?)",
              (roll_no, name, date, time))
    conn.commit()
    conn.close()

    export_to_excel()
    return jsonify({"status":"ok","message":"attendance marked", "roll_no": roll_no, "name": name})

# Export Excel
@app.route("/export")
def export_excel():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    export_to_excel()
    if os.path.exists(EXCEL_FILE):
        return send_file(EXCEL_FILE, as_attachment=True)
    return "No attendance data"

# Clear Attendance for Next Day
@app.route("/clear_attendance")
def clear_attendance():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    # Clear database
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM attendance")
    conn.commit()
    conn.close()

    # Remove Excel file and recreate empty
    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
    export_to_excel()

    return redirect(url_for("admin_dashboard"))

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Start
if __name__ == "__main__":
    init_db()
    export_to_excel()
    app.run(host='0.0.0.0', port=5000, debug=True)
