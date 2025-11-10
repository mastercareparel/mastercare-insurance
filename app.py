from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv, io, mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=os.getenv("DB_PORT")
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None



@app.route('/')
def index():
    # Agar user login nahi hai to login page par bhejna
    if 'user_id' not in session:
        return redirect('/login')
    return redirect('/form')  # agar login hai to form page par le jao


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        stored_password = password


        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, stored_password),
            )
            conn.commit()
            cursor.close()
            conn.close()
            return redirect("/login")

        except mysql.connector.Error as e:
            error = "Username already exists or MySQL error."

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password FROM users WHERE username=%s", (username,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and user[2] == password:
            session["user_id"] = user[0]
            return redirect("/form")
        else:
            error = "Invalid username or password."


    return render_template("login.html", error=error)



@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# -------------------- FORM & CRUD ROUTES --------------------
@app.route('/form')
def form_page():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('form.html')

@app.route("/add", methods=["POST"])
def add():
    if 'user_id' not in session:
        return redirect('/login')

    form = request.form

    new_entry = {
        "insurance": form.get("insurance"),
        "case_id": form.get("case_id"),
        "customer": form.get("customer"),
        "model": form.get("model"),
        "imei": form.get("imei"),
        "estimate": form.get("estimate"),
        "repair": form.get("repair"),
        "invoice": form.get("invoice"),
        "paymentDetails": form.get("paymentDetails"),
        "paymentValue": form.get("paymentValue"),
        "paymentDate": form.get("paymentDate"),
        "utr": form.get("utr"),
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO submissions (
            user_id, insurance, case_id, customer, model, imei,
            estimate, repair, invoice, paymentDetails, paymentValue,
            paymentDate, utr
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session['user_id'],
        form.get("insurance"),
        form.get("case_id"),
        form.get("customer"),
        form.get("model"),
        form.get("imei"),
        form.get("estimate"),
        form.get("repair"),
        form.get("invoice"),
        form.get("paymentDetails"),
        form.get("paymentValue"),
        form.get("paymentDate"),
        form.get("utr")      # 🔥 13th value
    ))


        conn.commit()

    except mysql.connector.Error as err:
        return f"Database error: {err}"

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("submissions_page"))

@app.route("/submissions")
def submissions_page():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = request.args.get("q", "").lower().strip()

    if query:
        cursor.execute("""
            SELECT * FROM submissions
            WHERE user_id = %s AND (
                LOWER(case_id) LIKE %s OR
                LOWER(imei) LIKE %s OR
                LOWER(customer) LIKE %s OR
                LOWER(insurance) LIKE %s OR
                LOWER(paymentValue) LIKE %s OR
                LOWER(utr) LIKE %s
            )
            ORDER BY id DESC
        """, (
            session['user_id'],
            f"%{query}%",
            f"%{query}%",
            f"%{query}%",
            f"%{query}%",
            f"%{query}%",
            f"%{query}%"
        ))
    else:
        cursor.execute("""
            SELECT * FROM submissions
            WHERE user_id = %s
            ORDER BY id DESC
        """, (session['user_id'],))

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("submissions.html", submissions=rows, search_query=query)

@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ delete only if submission belongs to logged in user
    cursor.execute("DELETE FROM submissions WHERE id=%s AND user_id=%s", 
                   (id, session["user_id"]))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/submissions')


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ FIRST check if record exists for that user
    cursor.execute("SELECT * FROM submissions WHERE id=%s AND user_id=%s", 
                   (id, session["user_id"]))
    data = cursor.fetchone()

    if not data:
        cursor.close()
        conn.close()
        return "Submission not found or not yours", 404

    # ✅ UPDATE logic
    if request.method == "POST":
        form = request.form

        cursor.execute("""
            UPDATE submissions SET
                insurance=%s,
                case_id=%s,
                customer=%s,
                model=%s,
                imei=%s,
                estimate=%s,
                repair=%s,
                invoice=%s,
                paymentDetails=%s,
                paymentValue=%s,
                paymentDate=%s,
                utr=%s
            WHERE id=%s AND user_id=%s
        """, (
            form.get("insurance"),
            form.get("case_id"),   # ✅ correct key
            form.get("customer"),
            form.get("model"),
            form.get("imei"),
            form.get("estimate"),
            form.get("repair"),
            form.get("invoice"),
            form.get("paymentDetails"),
            form.get("paymentValue"),
            form.get("paymentDate"),
            form.get("utr"),
            id,
            session["user_id"]
        ))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/submissions')

    cursor.close()
    conn.close()
    return render_template("edit.html", submission=data)



@app.route("/export_csv")
def export_csv():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM submissions WHERE user_id=%s", (session['user_id'],))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        return "No submissions to export.", 400

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Insurance", "Case ID", "Customer", "Model", "IMEI",
        "Estimate", "Repair", "Invoice", "Payment Details",
        "Payment Value", "Payment Date", "UTR"
    ])

    for s in rows:
        writer.writerow([
            s["insurance"], s["case_id"], s["customer"],
            s["model"],f"'{s['imei']}", s["estimate"], s["repair"],
            s["invoice"], s["paymentDetails"], s["paymentValue"],
            s["paymentDate"], s["utr"]
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=submissions.csv"

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Default 10000 for local, Render uses $PORT
    app.run(host="0.0.0.0", port=port)
