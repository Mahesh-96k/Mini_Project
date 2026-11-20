
import os
import tempfile
import uuid
import hashlib
import json
from datetime import date
from analysis_storage import (
    calculate_file_sha256,
    generate_internal_reference,
    parse_report_date,
    save_document_analysis,
)
from werkzeug.utils import secure_filename
from run_analysis import run_analysis
from datetime import timedelta
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

load_dotenv()

app = Flask(__name__)
# Private storage for original medical PDF files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVATE_UPLOAD_DIR = os.path.join(BASE_DIR, "private_uploads")

os.makedirs(PRIVATE_UPLOAD_DIR, exist_ok=True)

# Maximum uploaded PDF size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# Set SECRET_KEY in your .env file. Never use a public/default key.
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )


LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MediTrust Login</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f1f5f9;
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
        }
        .card {
            background: white;
            padding: 30px;
            width: min(360px, calc(100% - 60px));
            border-radius: 12px;
            box-shadow: 0 8px 30px #00000012;
        }
        h1 { color: #176b60; margin-bottom: 6px; }
        input, button {
            box-sizing: border-box;
            width: 100%;
            padding: 12px;
            margin-top: 12px;
            border-radius: 6px;
            font-size: 15px;
        }
        input { border: 1px solid #cbd5e1; }
        button {
            border: 0;
            background: #176b60;
            color: white;
            cursor: pointer;
        }
        .message { color: #b42318; }
        .muted { color: #64748b; font-size: 14px; }
    </style>
</head>
<body>
    <main class="card">
        <h1>MediTrust</h1>
        <p>Medical Report Verification</p>

        {% for message in get_flashed_messages() %}
            <p class="message">{{ message }}</p>
        {% endfor %}

        <form method="post" action="{{ url_for('login') }}">
            <label for="username">Username</label>
            <input id="username" name="username"
                   maxlength="100" autocomplete="username" required>

            <label for="password">Password</label>
            <input id="password" name="password" type="password"
                   autocomplete="current-password" required>

            <button type="submit">Log in</button>
        </form>

        <p class="muted">Use an account already registered in MediTrust.</p>
    </main>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MediTrust Dashboard</title>
</head>
<body>
    <h1>MediTrust Patient Dashboard</h1>
    <p>Welcome, {{ full_name }}!</p>
    <p>Full Name: {{ full_name }}</p>
    <p>Username: {{ username }}</p>
    <p>Global PID: {{ global_pid }}</p>
    <p>This is the initial dashboard. Document features will be added later.</p>

    <form method="post" action="{{ url_for('logout') }}">
        <button type="submit">Log out</button>
    </form>
</body>
</html>
"""


def login_required(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapped


def patient_required(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "patient":
            return "Forbidden: patient account required.", 403

        return view_function(*args, **kwargs)

    return wrapped

@app.route("/reset-session")
def reset_session():
    session.clear()
    return redirect(url_for("home"))

@app.route("/")
def home():
    if "user_id" in session:
        if session.get("role") == "patient":
            return redirect(url_for("dashboard"))

        if session.get("role") == "hospital":
            return redirect(url_for("hospital_dashboard"))

    return render_template("portal.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not app.config["SECRET_KEY"]:
        return "FLASK_SECRET_KEY is missing from .env.", 500

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT user_id, username, password_hash, role, is_active
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )

            user = cursor.fetchone()

        except mysql.connector.Error:
            app.logger.exception("Database error during login")
            return "Login is temporarily unavailable. Please try again.", 503

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

        # Use the same message for an unknown username or bad password.
        if (
            user is None
            or not user["is_active"]
            or not check_password_hash(user["password_hash"], password)
        ):
            flash("Invalid username or password.")
            return render_template("login.html"), 401

        if user["role"] != "patient":
            flash("This login page is for patient accounts.")
            return render_template("login.html"), 403

        # Clear any old session values before creating a new session.
        session.clear()
        session.permanent = True
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
@patient_required
def dashboard():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Derive the PID from the logged-in account, never from a URL.
        cursor.execute(
            """
            SELECT full_name, global_pid
            FROM patients
            WHERE user_id = %s
            """,
            (session["user_id"],),
        )
        patient = cursor.fetchone()

    except mysql.connector.Error:
        app.logger.exception("Database error loading patient dashboard")
        return "Dashboard is temporarily unavailable. Please try again.", 503

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    if patient is None:
        return "Patient profile not found.", 404

    return render_template(
        "dashboard.html",
        full_name=patient["full_name"],
        username=session["username"],
        global_pid=patient["global_pid"],
)


@app.route("/my-analyses")
@patient_required
def my_analyses():
    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    d.internal_reference,
                    d.created_at,
                    a.analysis_id,
                    a.risk_score,
                    a.risk_level,
                    a.review_status
                FROM medical_documents AS d
                JOIN analysis_results AS a
                    ON a.document_id = d.document_id
                JOIN patients AS p
                    ON p.patient_id = d.patient_id
                WHERE p.user_id = %s
                ORDER BY d.created_at DESC
                """,
                (session["user_id"],),
            )
            analyses = cursor.fetchall()

        finally:
            cursor.close()

        return render_template(
            "my_analyses.html",
            analyses=analyses,
        )

    finally:
        connection.close()


@app.route("/my-analyses/<int:analysis_id>")
@patient_required
def analysis_details(analysis_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                d.internal_reference,
                d.created_at,
                a.analysis_id,
                a.extracted_data,
                a.risk_score,
                a.risk_level,
                a.review_status,
                a.findings
            FROM analysis_results AS a
            JOIN medical_documents AS d
                ON d.document_id = a.document_id
            JOIN patients AS p
                ON p.patient_id = d.patient_id
            WHERE a.analysis_id = %s
              AND p.user_id = %s
            """,
            (analysis_id, session["user_id"]),
        )

        analysis = cursor.fetchone()

        if analysis is None:
            return "Analysis not found.", 404

        
        cursor.execute(
            """
            SELECT hospital_id, hospital_name, city
            FROM hospitals
            WHERE is_demo = TRUE
            ORDER BY hospital_name
            """
        )
        demo_hospitals = cursor.fetchall()

        return render_template(
            "analysis_details.html",
            analysis=analysis,
            demo_hospitals=demo_hospitals,
        )


    except mysql.connector.Error:
        app.logger.exception("Database error loading analysis details")
        return "Analysis details are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


@app.route("/request-hospital-access", methods=["POST"])
@patient_required
def request_hospital_access():
    analysis_id = request.form.get("analysis_id", type=int)
    hospital_id = request.form.get("hospital_id", "").strip()

    if not analysis_id or not hospital_id:
        flash("Please select a document and hospital.")
        return redirect(url_for("my_analyses"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Confirm the selected analysis belongs to this patient.
        cursor.execute(
            """
            SELECT d.document_id, d.patient_id
            FROM analysis_results AS a
            JOIN medical_documents AS d
                ON d.document_id = a.document_id
            JOIN patients AS p
                ON p.patient_id = d.patient_id
            WHERE a.analysis_id = %s
              AND p.user_id = %s
            """,
            (analysis_id, session["user_id"]),
        )
        document = cursor.fetchone()

        if document is None:
            flash("The selected analysis could not be found.")
            return redirect(url_for("my_analyses"))

        # Confirm the hospital exists. Demo hospitals are allowed
        # during development, as requested.
        cursor.execute(
            """
            SELECT hospital_id
            FROM hospitals
            WHERE hospital_id = %s
              AND is_demo = TRUE
            """,
            (hospital_id,),
        )
        hospital = cursor.fetchone()

        if hospital is None:
            flash("Please select a valid demo hospital.")
            return redirect(url_for("analysis_details", analysis_id=analysis_id))

        # Prevent a duplicate active request for this document/hospital.
        cursor.execute(
            """
            SELECT request_id
            FROM access_requests
            WHERE patient_id = %s
              AND document_id = %s
              AND hospital_id = %s
              AND status = 'pending'
              AND expires_at > CURRENT_TIMESTAMP
            LIMIT 1
            """,
            (document["patient_id"], document["document_id"], hospital_id),
        )

        if cursor.fetchone():
            flash("A pending request already exists for this hospital and document.")
            return redirect(url_for("analysis_details", analysis_id=analysis_id))

        # Create a request that expires in 7 days.
        cursor.execute(
            """
            INSERT INTO access_requests
                (patient_id, document_id, hospital_id, status, expires_at)
            VALUES
                (%s, %s, %s, 'pending', DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 7 DAY))
            """,
            (document["patient_id"], document["document_id"], hospital_id),
        )

        connection.commit()
        flash("Hospital access request submitted successfully.")

        return redirect(url_for("analysis_details", analysis_id=analysis_id))

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Failed to create hospital access request")
        flash("Could not submit the request. Please try again.")
        return redirect(url_for("my_analyses"))

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


@app.route("/hospital-access-request/<int:request_id>/decide", methods=["POST"])
@login_required
def decide_hospital_access_request(request_id):
    if session.get("role") != "hospital":
        return "Forbidden: hospital account required.", 403

    action = request.form.get("action", "").strip().lower()

    if action not in ("approve", "reject"):
        flash("Invalid request action.")
        return redirect(url_for("hospital_dashboard"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT ar.request_id, ar.status, ar.expires_at
            FROM access_requests AS ar
            JOIN users AS u
                ON u.hospital_id = ar.hospital_id
            WHERE ar.request_id = %s
              AND u.user_id = %s
              AND u.role = 'hospital'
              AND u.is_active = 1
            FOR UPDATE
            """,
            (request_id, session["user_id"]),
        )

        access_request = cursor.fetchone()

        if access_request is None:
            connection.rollback()
            return "Request not found.", 404

        if access_request["status"] != "pending":
            connection.rollback()
            flash("This request has already been decided or is no longer pending.")
            return redirect(url_for("hospital_dashboard"))

        cursor.execute(
            """
            UPDATE access_requests
            SET status = %s,
                decided_at = CURRENT_TIMESTAMP
            WHERE request_id = %s
              AND status = 'pending'
              AND expires_at > CURRENT_TIMESTAMP
            """,
            (
                "approved" if action == "approve" else "rejected",
                request_id,
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            flash("This request has expired or is no longer pending.")
            return redirect(url_for("hospital_dashboard"))

        connection.commit()
        flash(
            "Request approved."
            if action == "approve"
            else "Request rejected."
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Failed to decide hospital access request")
        flash("Could not update the request. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    return redirect(url_for("hospital_dashboard"))



@app.route("/hospital-login", methods=["GET", "POST"])
def hospital_login():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT hospital_id, hospital_name
            FROM hospitals
            WHERE is_demo = TRUE
            ORDER BY hospital_name
            """
        )
        hospitals = cursor.fetchall()

        if request.method == "POST":
            hospital_id = request.form.get("hospital_id", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            cursor.execute(
                """
                SELECT user_id, username, password_hash,
                       role, hospital_id, is_active
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )
            user = cursor.fetchone()

            # Validate the selected hospital and account.
            selected_hospital = any(
                h["hospital_id"] == hospital_id
                for h in hospitals
            )

            valid_account = (
                user is not None
                and user["is_active"]
                and user["role"] == "hospital"
                and user["hospital_id"] == hospital_id
                and check_password_hash(
                    user["password_hash"], password
                )
            )

            if not selected_hospital or not valid_account:
                flash("Invalid hospital selection or login credentials.")
            else:
                session.clear()
                session.permanent = True
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                session["role"] = "hospital"
                session["hospital_id"] = user["hospital_id"]

                return redirect(url_for("hospital_dashboard"))

    except mysql.connector.Error:
        app.logger.exception("Hospital login database error")
        return "Hospital login is temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    return render_template(
        "hospital_login.html",
        hospitals=hospitals,
    )


@app.route("/hospital-dashboard")
@login_required
def hospital_dashboard():
    if session.get("role") != "hospital":
        return "Forbidden: hospital account required.", 403

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                h.hospital_id,
                h.hospital_name,
                h.city,
                h.district,
                h.state,
                h.is_demo,
                h.is_approved
            FROM users AS u
            JOIN hospitals AS h
                ON h.hospital_id = u.hospital_id
            WHERE u.user_id = %s
              AND u.role = 'hospital'
              AND u.is_active = 1
            """,
            (session["user_id"],),
        )

        hospital = cursor.fetchone()

        if hospital is None:
            return "Hospital account not found or inactive.", 404

        cursor.execute(
            """
            SELECT
                ar.request_id,
                ar.patient_id,
                ar.document_id,
                d.internal_reference,
                ar.status,
                ar.requested_at,
                ar.expires_at
            FROM access_requests AS ar
            JOIN medical_documents AS d
                ON d.document_id = ar.document_id
            WHERE ar.hospital_id = %s
            ORDER BY
                CASE WHEN ar.status = 'pending' THEN 0 ELSE 1 END,
                ar.requested_at DESC
            """,
            (hospital["hospital_id"],),
        )

        access_requests = cursor.fetchall()

        return render_template(
            "hospital_dashboard.html",
            hospital=hospital,
            username=session.get("username", ""),
            access_requests=access_requests,
        )

    except mysql.connector.Error:
        app.logger.exception("Error loading hospital dashboard")
        return "Hospital dashboard is temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/verify-document", methods=["GET", "POST"])
@patient_required
def verify_document():
    if request.method == "GET":
        return render_template("verify_document.html")

    uploaded_file = request.files.get("report")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a PDF report.")
        return redirect(url_for("verify_document"))

    # Check the file extension.
    safe_name = secure_filename(uploaded_file.filename)
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        flash("Only PDF files are allowed.")
        return redirect(url_for("verify_document"))

    # Check the PDF signature; the browser's MIME type is not trusted.
    uploaded_file.stream.seek(0)
    signature = uploaded_file.stream.read(5)
    uploaded_file.stream.seek(0)

    if signature != b"%PDF-":
        flash("The selected file does not appear to be a valid PDF.")
        return redirect(url_for("verify_document"))

    temporary_path = None

    try:
        # Use a private temporary file, never the public static folder.
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pdf", delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
            uploaded_file.save(temporary_path)

        # Run the existing extraction, Gemini, and Python checks.
        result = run_analysis(temporary_path)

        # Identify the authenticated patient.
        connection = get_connection()

        try:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(
                    """
                    SELECT patient_id
                    FROM patients
                    WHERE user_id = %s
                    """,
                    (session["user_id"],),
                )
                patient = cursor.fetchone()
            finally:
                cursor.close()

            if patient is None:
                raise RuntimeError("Patient profile not found.")

            print("Authenticated patient ID:", patient["patient_id"])

            extracted_data = result.get("extracted_data", {})
            report_number = extracted_data.get("report_number")

            internal_reference = generate_internal_reference()
            print("Internal MediTrust reference:", internal_reference)

            # Generate a private filename; never use the user's filename for storage.
            stored_file_name = f"{uuid.uuid4().hex}.pdf"
            private_file_path = os.path.join(PRIVATE_UPLOAD_DIR, stored_file_name)

            file_sha256 = calculate_file_sha256(temporary_path)


            report_date = parse_report_date(
                extracted_data.get("report_date")
            )


            database_committed = False

            try:
                # Move the original PDF into private storage.
                # If this fails, the temporary file remains available
                # for the existing cleanup block.
                os.replace(temporary_path, private_file_path)
                temporary_path = None

                # Save the filename and analysis in MySQL.
                save_result = save_document_analysis(
                    connection=connection,
                    patient_id=patient["patient_id"],
                    hospital_id=None,
                    internal_reference=internal_reference,
                    uploaded_by=session["user_id"],
                    report_number=(
                        report_number.strip()
                        if isinstance(report_number, str)
                        and report_number.strip()
                        else None
                    ),
                    document_type="PATIENT_SUBMITTED_UNVERIFIED",
                    report_date=report_date,
                    stored_file_name=stored_file_name,
                    file_sha256=file_sha256,
                    result=result,
                )

                connection.commit()
                database_committed = True

                print(
                    "Saved MediTrust document ID:",
                    save_result["document_id"],
                )
                print(
                    "Saved analysis ID:",
                    save_result["analysis_id"],
                )

                result["internal_reference"] = internal_reference
                result["document_id"] = save_result["document_id"]
                result["analysis_id"] = save_result["analysis_id"]

            except Exception:
                if not database_committed:
                    try:
                        connection.rollback()
                    except Exception:
                        app.logger.exception(
                            "Database rollback failed during PDF upload"
                        )

                    # Remove the stored PDF if the database save failed.
                    if os.path.exists(private_file_path):
                        try:
                            os.remove(private_file_path)
                        except OSError:
                            app.logger.exception(
                                "Could not remove PDF after failed database save"
                            )

                raise

            extracted_data = result.get("extracted_data", {})
            report_number = extracted_data.get("report_number")


        finally:
            connection.close()
        

        return render_template(
            "analysis_result.html",
            result=result,
            original_filename=safe_name
        )

    except Exception:
        app.logger.exception("Medical document analysis failed")
        flash("Analysis could not be completed. Please try again.")
        return redirect(url_for("verify_document"))

    finally:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                app.logger.exception("Could not remove temporary upload")


if __name__ == "__main__":
    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "Add FLASK_SECRET_KEY to your .env file before starting MediTrust."
        )

    # Local development only. Do not expose the debug server publicly.
    app.run(debug=True)
