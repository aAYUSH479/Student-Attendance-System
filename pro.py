from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3, qrcode, io, json, pandas as pd, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"
DB = "attendance.db"

# ----------- Initialize DB with Predefined Students -------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  roll_no TEXT,
                  name TEXT,
                  password TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  roll_no TEXT,
                  name TEXT,
                  date TEXT,
                  time TEXT)''')
    
    # Predefined students (name, roll_no)
    predefined = [
        ("Ayush Singh", "101"),
        ("Rohan Kumar", "102"),
        ("Priya Sharma", "103")
    ]
    
    for name, roll in predefined:
        password = name[:4].upper() + "123"
        # Insert only if not exists
        c.execute("SELECT * FROM students WHERE roll_no=?", (roll,))
        if not c.fetchone():
            c.execute("INSERT INTO students (roll_no, name, password) VALUES (?, ?, ?)", 
                      (roll, name, password))
    
    conn.commit()
    conn.close()

# ----------- Routes -------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE name=? AND password=?", (name, password))
        student = c.fetchone()
        conn.close()

        if student:
            session["student"] = {"roll_no": student[1], "name": student[2]}
            return redirect(url_for("student_dashboard"))
        elif name=="admin" and password=="admin123":  # Admin login
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials!")
    return render_template("login.html")

@app.route("/student")
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("login"))
    return render_template("student.html", student=session["student"])

@app.route("/student_qr")
def student_qr():
    if "student" not in session:
        return redirect(url_for("login"))
    
    student = session["student"]
    data = {"roll_no": student["roll_no"], "name": student["name"]}
    
    img = qrcode.make(json.dumps(data))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/admin")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM attendance")
    records = c.fetchall()
    conn.close()
    return render_template("admin.html", records=records)

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    if "admin" not in session:
        return redirect(url_for("login"))

    qr_data = request.form["qr_data"]
    student = json.loads(qr_data)

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    c.execute("INSERT INTO attendance (roll_no, name, date, time) VALUES (?,?,?,?)",
              (student["roll_no"], student["name"], date, time))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/export")
def export_excel():
    if "admin" not in session:
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM attendance", conn)
    conn.close()

    filename = "attendance.xlsx"
    df.to_excel(filename, index=False)
    return send_file(filename, as_attachment=True)

# ----------- Start -------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
