from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv, io, mysql.connector

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Temporary in-memory data
submissions = []

# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",          # apna MySQL username
        password="Manu@2046",          # apna MySQL password
        database="mastercare" # apna database name
    )


@app.route('/')
def index():
    # Agar user login nahi hai to login page par bhejna
    if 'user_id' not in session:
        return redirect('/login')
    return redirect('/form')  # agar login hai to form page par le jao


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            return redirect('/login')
        except mysql.connector.Error:
            return "⚠️ Username already exists or database error."
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect('/form')
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')


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
        "created": datetime.now().strftime("%d/%m/%Y, %I:%M:%S %p"),
        "insurance": form.get("insurance"),
        "caseId": form.get("caseId"),
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
    submissions.append(new_entry)
    return redirect(url_for("submissions_page"))


@app.route("/submissions")
def submissions_page():
    if 'user_id' not in session:
        return redirect('/login')

    query = request.args.get("q", "").lower().strip()
    if query:
        filtered = [
            s for s in submissions
            if query in s.get("caseId", "").lower()
            or query in s.get("imei", "").lower()
            or query in s.get("customer", "").lower()
            or query in s.get("insurance", "").lower()
            or query in s.get("paymentValue", "").lower()
            or query in s.get("utr", "").lower()
        ]
    else:
        filtered = submissions
    return render_template("submissions.html", submissions=filtered, search_query=query)


@app.route("/delete/<int:index>")
def delete(index):
    if 'user_id' not in session:
        return redirect('/login')
    if 0 <= index < len(submissions):
        submissions.pop(index)
    return redirect(url_for("submissions_page"))


@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit(index):
    if 'user_id' not in session:
        return redirect('/login')

    if 0 <= index < len(submissions):
        if request.method == "POST":
            form = request.form
            submissions[index] = {
                "created": submissions[index]["created"],
                "insurance": form.get("insurance"),
                "caseId": form.get("caseId"),
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
            return redirect(url_for("submissions_page"))
        data = submissions[index]
        return render_template("edit.html", submission=data, index=index)
    return "Invalid index", 404


@app.route("/export_csv")
def export_csv():
    """Export all submissions to a CSV file."""
    if not submissions:
        return "No submissions available to export.", 400

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Created", "Insurance", "Case ID", "Customer", "Model", "IMEI",
        "Estimate", "Repair", "Invoice", "Payment Details",
        "Payment Value", "Payment Date", "UTR"
    ])

    for s in submissions:
        # 🧠 Fix: Convert payment date to proper yyyy-mm-dd format
        raw_date = s.get("paymentDate", "").strip()
        payment_date = ""

        # Try to fix the format
        if raw_date:
            parts = raw_date.replace("/", "-").split("-")
            if len(parts) == 3:
                d, m, y = parts
                if len(y) == 2:  # e.g., 06-11-25
                    y = "20" + y
                # make sure it's in yyyy-mm-dd (Excel-friendly)
                payment_date = f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
            else:
                payment_date = raw_date

        writer.writerow([
            s.get("created", ""),
            s.get("insurance", ""),
            s.get("caseId", ""),
            s.get("customer", ""),
            s.get("model", ""),
            s.get("imei", ""),
            s.get("estimate", ""),
            s.get("repair", ""),
            s.get("invoice", ""),
            s.get("paymentDetails", ""),
            s.get("paymentValue", ""),
            payment_date,
            s.get("utr", "")
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True)
