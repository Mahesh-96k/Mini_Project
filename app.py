
import os
import tempfile

import uuid
import hashlib
import json
from datetime import date, datetime
from analysis_storage import (
    calculate_file_sha256,
    generate_internal_reference,
    parse_report_date,
    save_document_analysis,
)
from werkzeug.utils import secure_filename
from run_analysis import run_analysis
from document_analyzer import summarize_medical_report
from ai_health_advisor import generate_measurement_insight, answer_followup_question
from health_history_pdf import generate_health_history_pdf
from email_service import (
    generate_and_store_otp,
    verify_otp as verify_otp_service,
    send_otp_email,
    send_health_report_email,
)
from datetime import timedelta
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    send_file,
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
                SELECT user_id, username, email, password_hash, role, is_active
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

        # Two-Step Verification (2FA)
        session.clear()
        session["pending_2fa_user_id"] = user["user_id"]
        session["pending_2fa_username"] = user["username"]
        session["pending_2fa_role"] = user["role"]

        user_email = (user.get("email") or "").strip()

        if user_email:
            session["pending_2fa_email"] = user_email
            connection = None
            try:
                connection = get_connection()
                otp_code = generate_and_store_otp(connection, user["user_id"], purpose="login")
                send_otp_email(user_email, otp_code, username=user["username"])
            except Exception:
                app.logger.exception("Failed to send 2FA OTP")
                flash("Could not generate security code. Please try again.")
                return redirect(url_for("login"))
            finally:
                if connection is not None:
                    connection.close()

            flash("A 6-digit security code has been sent to your registered email.")
            return redirect(url_for("verify_otp"))
        else:
            # Account doesn't have an email yet; prompt patient to provide one
            return redirect(url_for("verify_otp", need_email=1))

    return render_template("login.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    pending_user_id = session.get("pending_2fa_user_id")
    if not pending_user_id:
        flash("Please sign in first to continue.")
        return redirect(url_for("login"))

    pending_email = session.get("pending_2fa_email")
    need_email = request.args.get("need_email") == "1" or not pending_email

    if request.method == "POST":
        action = request.form.get("action", "verify").strip()
        connection = None

        try:
            connection = get_connection()

            # Action 1: Set email if not already on file
            if action == "set_email":
                new_email = request.form.get("email", "").strip().lower()
                if not new_email or "@" not in new_email:
                    flash("Please provide a valid email address.")
                    return render_template("verify_otp.html", need_email=True, email=None)

                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "UPDATE users SET email = %s WHERE user_id = %s",
                    (new_email, pending_user_id)
                )
                connection.commit()
                cursor.close()

                session["pending_2fa_email"] = new_email
                otp_code = generate_and_store_otp(connection, pending_user_id, purpose="login")
                send_otp_email(new_email, otp_code, username=session.get("pending_2fa_username", "Patient"))
                flash(f"Email registered! A 6-digit security code has been sent to {new_email}.")
                return redirect(url_for("verify_otp"))

            # Action 2: Resend OTP
            elif action == "resend":
                if not pending_email:
                    return redirect(url_for("verify_otp", need_email=1))

                otp_code = generate_and_store_otp(connection, pending_user_id, purpose="login")
                send_otp_email(pending_email, otp_code, username=session.get("pending_2fa_username", "Patient"))
                flash("A new security code has been sent to your email.")
                return redirect(url_for("verify_otp"))

            # Action 3: Verify OTP code
            else:
                submitted_code = request.form.get("otp_code", "").strip()
                is_valid, message = verify_otp_service(connection, pending_user_id, submitted_code, purpose="login")

                if is_valid:
                    # Upgrade session to fully authenticated
                    session.permanent = True
                    session["user_id"] = session["pending_2fa_user_id"]
                    session["username"] = session["pending_2fa_username"]
                    session["role"] = session["pending_2fa_role"]

                    session.pop("pending_2fa_user_id", None)
                    session.pop("pending_2fa_username", None)
                    session.pop("pending_2fa_role", None)
                    session.pop("pending_2fa_email", None)

                    flash("Sign in successful! Two-step verification complete.")
                    return redirect(url_for("dashboard"))
                else:
                    flash(message)
                    return render_template("verify_otp.html", need_email=False, email=pending_email)

        except mysql.connector.Error:
            app.logger.exception("Database error during OTP verification")
            flash("Database service error. Please try again.")
            return render_template("verify_otp.html", need_email=need_email, email=pending_email)
        finally:
            if connection is not None:
                connection.close()

    return render_template("verify_otp.html", need_email=need_email, email=pending_email)

    return render_template("login.html")


@app.route("/dashboard")
@patient_required
def dashboard():
    connection = None
    cursor = None
    recent_analyses = []
    recent_measurements = []
    analyses_count = 0
    measurements_count = 0

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Derive the PID from the logged-in account, never from a URL.
        cursor.execute(
            """
            SELECT patient_id, full_name, global_pid
            FROM patients
            WHERE user_id = %s
            """,
            (session["user_id"],),
        )
        patient = cursor.fetchone()

        if patient is not None:
            patient_id = patient["patient_id"]

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM medical_documents
                WHERE patient_id = %s
                """,
                (patient_id,)
            )
            doc_res = cursor.fetchone()
            analyses_count = doc_res["count"] if doc_res else 0

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM health_measurements
                WHERE patient_id = %s
                """,
                (patient_id,)
            )
            meas_res = cursor.fetchone()
            measurements_count = meas_res["count"] if meas_res else 0

            cursor.execute(
                """
                SELECT a.analysis_id, d.internal_reference, a.risk_score, a.risk_level, a.review_status, d.created_at
                FROM analysis_results a
                JOIN medical_documents d ON a.document_id = d.document_id
                WHERE d.patient_id = %s
                ORDER BY d.created_at DESC
                LIMIT 3
                """,
                (patient_id,)
            )
            recent_analyses = cursor.fetchall()

            cursor.execute(
                """
                SELECT measurement_type, value, secondary_value, unit, recorded_at
                FROM health_measurements
                WHERE patient_id = %s
                ORDER BY recorded_at DESC
                LIMIT 4
                """,
                (patient_id,)
            )
            recent_measurements = cursor.fetchall()

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
        analyses_count=analyses_count,
        measurements_count=measurements_count,
        recent_analyses=recent_analyses,
        recent_measurements=recent_measurements,
    )


@app.route("/health-manager")
@patient_required
def health_manager():
    return render_template("health_manager.html")


@app.route("/health-manager/blood-sugar", methods=["GET", "POST"])
@patient_required
def blood_sugar():
    connection = None
    cursor = None

    measurement_types = {
        "fasting": "Fasting Blood Sugar",
        "post_meal": "Post-Meal Blood Sugar",
        "random": "Random Blood Sugar",
        "hba1c": "HbA1c"
    }

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get the logged-in patient's database ID.
        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            measurement_type = request.form.get(
                "measurement_type", ""
            ).strip()

            value_text = request.form.get("value", "").strip()
            recorded_at = request.form.get("recorded_at", "").strip()
            context = request.form.get("context", "").strip()

            if measurement_type not in measurement_types:
                flash("Please select a valid measurement type.")

            else:
                try:
                    value = float(value_text)

                    if not (0 < value <= 10000):
                        raise ValueError

                    
                    recorded_datetime = datetime.strptime(
                    recorded_at, "%Y-%m-%dT%H:%M"
                    )

                    if recorded_datetime > datetime.now():
                        flash("Future dates are not allowed. Please select today or an earlier date.")
                        return redirect(url_for("blood_sugar"))

                    unit = "%" if measurement_type == "hba1c" else "mg/dL"

                    cursor.execute(
                        """
                        INSERT INTO health_measurements
                        (patient_id, measurement_type, value,
                         unit, context, recorded_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            patient_id,
                            "blood_sugar_" + measurement_type,
                            value,
                            unit,
                            context or None,
                            recorded_at.replace("T", " ")
                        )
                    )

                    connection.commit()
                    flash("Blood sugar measurement saved successfully.")

                except ValueError:
                    flash("Please enter a valid measurement and date.")

            return redirect(url_for("blood_sugar"))

        # Fetch only this patient's blood sugar records.
        cursor.execute(
            """
            SELECT measurement_id,measurement_type, value, unit,
                   context, recorded_at, uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type IN (
                  'blood_sugar_fasting',
                  'blood_sugar_post_meal',
                  'blood_sugar_random',
                  'blood_sugar_hba1c'
              )
            ORDER BY recorded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        latest_by_type = {}
        previous_by_type = {}

        for record in measurements:
            measurement_type = record["measurement_type"]

            if measurement_type not in latest_by_type:
                latest_by_type[measurement_type] = record

            elif measurement_type not in previous_by_type:
                previous_by_type[measurement_type] = record


       

        return render_template(
            "blood_sugar.html",
            measurements=measurements,
            measurement_types=measurement_types,
            latest_by_type=latest_by_type,
            previous_by_type=previous_by_type,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Blood sugar database error")
        return "Blood sugar records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()
@app.route("/health-manager/blood-sugar/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_blood_sugar(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Identify the logged-in patient.
        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        # Delete only the selected record belonging to this patient.
        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type IN (
                  'blood_sugar_fasting',
                  'blood_sugar_post_meal',
                  'blood_sugar_random',
                  'blood_sugar_hba1c'
              )
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Blood sugar record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Blood sugar deletion error")
        flash("Unable to delete the record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("blood_sugar"))

@app.route("/health-manager/blood-pressure", methods=["GET", "POST"])
@patient_required
def blood_pressure():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            systolic_text = request.form.get("systolic", "").strip()
            diastolic_text = request.form.get("diastolic", "").strip()
            recorded_at = request.form.get("recorded_at", "").strip()
            context = request.form.get("context", "").strip()

            try:
                systolic = int(systolic_text)
                diastolic = int(diastolic_text)

                if not (1 <= systolic <= 300 and 1 <= diastolic <= 200):
                    raise ValueError

                if systolic <= diastolic:
                    flash("Systolic pressure must be higher than diastolic pressure.")
                    return redirect(url_for("blood_pressure"))

                recorded_datetime = datetime.strptime(
                    recorded_at, "%Y-%m-%dT%H:%M"
                )

                if recorded_datetime > datetime.now():
                    flash("Future dates are not allowed.")
                    return redirect(url_for("blood_pressure"))

                cursor.execute(
                    """
                    INSERT INTO health_measurements
                    (patient_id, measurement_type, value,
                     secondary_value, unit, context, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient_id,
                        "blood_pressure",
                        systolic,
                        diastolic,
                        "mmHg",
                        context or None,
                        recorded_at.replace("T", " ")
                    )
                )

                connection.commit()
                flash("Blood pressure measurement saved successfully.")

            except ValueError:
                flash("Please enter valid blood pressure values and date.")

            return redirect(url_for("blood_pressure"))

        cursor.execute(
            """
            SELECT measurement_id, measurement_type, value,
                   secondary_value, unit, context,
                   recorded_at, uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type = 'blood_pressure'
            ORDER BY recorded_at DESC, uploaded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        latest = measurements[0] if measurements else None
        previous = measurements[1] if len(measurements) > 1 else None

        return render_template(
            "blood_pressure.html",
            measurements=measurements,
            latest=latest,
            previous=previous,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Blood pressure database error")
        return "Blood pressure records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@app.route("/health-manager/blood-pressure/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_blood_pressure(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type = 'blood_pressure'
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Blood pressure record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Blood pressure deletion error")
        flash("Unable to delete the record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("blood_pressure"))

@app.route("/health-manager/heart-rate", methods=["GET", "POST"])
@patient_required
def heart_rate():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            value_text = request.form.get("value", "").strip()
            recorded_at = request.form.get("recorded_at", "").strip()
            context = request.form.get("context", "").strip()

            try:
                value = int(value_text)

                if not (1 <= value <= 300):
                    raise ValueError

                recorded_datetime = datetime.strptime(
                    recorded_at, "%Y-%m-%dT%H:%M"
                )

                if recorded_datetime > datetime.now():
                    flash("Future dates are not allowed.")
                    return redirect(url_for("heart_rate"))

                cursor.execute(
                    """
                    INSERT INTO health_measurements
                    (patient_id, measurement_type, value,
                     unit, context, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient_id,
                        "heart_rate",
                        value,
                        "BPM",
                        context or None,
                        recorded_at.replace("T", " ")
                    )
                )

                connection.commit()
                flash("Heart rate measurement saved successfully.")

            except ValueError:
                flash("Please enter a valid heart rate and date.")

            return redirect(url_for("heart_rate"))

        cursor.execute(
            """
            SELECT measurement_id, measurement_type, value,
                   unit, context, recorded_at, uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type = 'heart_rate'
            ORDER BY recorded_at DESC, uploaded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        latest = measurements[0] if measurements else None
        previous = measurements[1] if len(measurements) > 1 else None

        return render_template(
            "heart_rate.html",
            measurements=measurements,
            latest=latest,
            previous=previous,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Heart rate database error")
        return "Heart rate records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@app.route("/health-manager/heart-rate/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_heart_rate(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type = 'heart_rate'
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Heart rate record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Heart rate deletion error")
        flash("Unable to delete the record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("heart_rate"))

@app.route("/health-manager/weight", methods=["GET", "POST"])
@patient_required
def weight_tracking():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            value_text = request.form.get("value", "").strip()
            recorded_at = request.form.get("recorded_at", "").strip()
            context = request.form.get("context", "").strip()

            try:
                value = float(value_text)

                if not (0.1 <= value <= 500):
                    raise ValueError

                recorded_datetime = datetime.strptime(
                    recorded_at, "%Y-%m-%dT%H:%M"
                )

                if recorded_datetime > datetime.now():
                    flash("Future dates are not allowed.")
                    return redirect(url_for("weight_tracking"))

                cursor.execute(
                    """
                    INSERT INTO health_measurements
                    (patient_id, measurement_type, value,
                     unit, context, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient_id,
                        "weight",
                        value,
                        "kg",
                        context or None,
                        recorded_at.replace("T", " ")
                    )
                )

                connection.commit()
                flash("Weight measurement saved successfully.")

            except ValueError:
                flash("Please enter a valid weight and date.")

            return redirect(url_for("weight_tracking"))

        cursor.execute(
            """
            SELECT measurement_id, measurement_type, value,
                   unit, context, recorded_at, uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type = 'weight'
            ORDER BY recorded_at DESC, uploaded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        latest = measurements[0] if measurements else None
        previous = measurements[1] if len(measurements) > 1 else None

        return render_template(
            "weight_tracking.html",
            measurements=measurements,
            latest=latest,
            previous=previous,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Weight database error")
        return "Weight records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()
@app.route("/health-manager/weight/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_weight(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type = 'weight'
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Weight record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Weight deletion error")
        flash("Unable to delete the record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("weight_tracking"))



@app.route("/health-manager/sleep", methods=["GET", "POST"])
@patient_required
def sleep_tracking():
    connection = None
    cursor = None

    def get_sleep_indicator(duration, efficiency):
        if 7 <= duration <= 9 and efficiency >= 85:
            return "Good"
        elif 6 <= duration <= 10 and efficiency >= 75:
            return "Average"
        else:
            return "Needs Attention"

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            sleep_start = request.form.get("sleep_start", "").strip()
            wake_up = request.form.get("wake_up", "").strip()
            awake_text = request.form.get("awake_minutes", "").strip()
            context = request.form.get("context", "").strip()

            try:
                start_datetime = datetime.strptime(
                    sleep_start, "%Y-%m-%dT%H:%M"
                )
                end_datetime = datetime.strptime(
                    wake_up, "%Y-%m-%dT%H:%M"
                )
                awake_minutes = int(awake_text)

                time_in_bed = (
                    end_datetime - start_datetime
                ).total_seconds() / 60

                if start_datetime > datetime.now() or end_datetime > datetime.now():
                    raise ValueError("Future dates are not allowed.")

                if not (0 < time_in_bed <= 1440):
                    raise ValueError("Invalid sleep session.")

                if not (0 <= awake_minutes < time_in_bed):
                    raise ValueError("Invalid awake time.")

                actual_sleep_minutes = time_in_bed - awake_minutes
                sleep_hours = actual_sleep_minutes / 60

                efficiency = (
                    actual_sleep_minutes / time_in_bed
                ) * 100

                efficiency = round(efficiency, 2)
                sleep_hours = round(sleep_hours, 2)

                cursor.execute(
                    """
                    INSERT INTO health_measurements
                    (
                        patient_id,
                        measurement_type,
                        value,
                        secondary_value,
                        unit,
                        context,
                        recorded_at,
                        ended_at,
                        awake_minutes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient_id,
                        "sleep_duration",
                        sleep_hours,
                        efficiency,
                        "hours",
                        context or None,
                        start_datetime,
                        end_datetime,
                        awake_minutes
                    )
                )

                connection.commit()
                flash("Sleep session saved successfully.")

            except ValueError as error:
                flash(str(error) or "Please enter valid sleep details.")

            return redirect(url_for("sleep_tracking"))

        cursor.execute(
            """
            SELECT
                measurement_id,
                measurement_type,
                value,
                secondary_value,
                unit,
                context,
                recorded_at,
                ended_at,
                awake_minutes,
                uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type = 'sleep_duration'
            ORDER BY recorded_at DESC, uploaded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        for record in measurements:
            duration = float(record["value"])
            efficiency = float(record["secondary_value"] or 0)

            record["sleep_quality"] = get_sleep_indicator(
                duration, efficiency
            )

        latest = measurements[0] if measurements else None
        previous = measurements[1] if len(measurements) > 1 else None

        return render_template(
            "sleep_tracking.html",
            measurements=measurements,
            latest=latest,
            previous=previous,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Sleep tracking database error")
        return "Sleep records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()



@app.route("/health-manager/sleep/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_sleep(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type = 'sleep_duration'
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Sleep record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Sleep deletion error")
        flash("Unable to delete the record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("sleep_tracking"))


@app.route("/health-manager/temperature", methods=["GET", "POST"])
@patient_required
def temperature_tracking():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient["patient_id"]

        if request.method == "POST":
            value_text = request.form.get("value", "").strip()
            recorded_at = request.form.get("recorded_at", "").strip()
            context = request.form.get("context", "").strip()

            try:
                temperature = float(value_text)

                if not (25 <= temperature <= 45):
                    raise ValueError

                recorded_datetime = datetime.strptime(
                    recorded_at, "%Y-%m-%dT%H:%M"
                )

                if recorded_datetime > datetime.now():
                    flash("Future dates are not allowed.")
                    return redirect(url_for("temperature_tracking"))

                cursor.execute(
                    """
                    INSERT INTO health_measurements
                    (
                        patient_id,
                        measurement_type,
                        value,
                        unit,
                        context,
                        recorded_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient_id,
                        "temperature",
                        temperature,
                        "°C",
                        context or None,
                        recorded_datetime
                    )
                )

                connection.commit()
                flash("Temperature record saved successfully.")

            except ValueError:
                flash("Enter a valid temperature between 25°C and 45°C and a valid date.")

            return redirect(url_for("temperature_tracking"))

        cursor.execute(
            """
            SELECT
                measurement_id,
                measurement_type,
                value,
                unit,
                context,
                recorded_at,
                uploaded_at
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type = 'temperature'
            ORDER BY recorded_at DESC, uploaded_at DESC
            """,
            (patient_id,)
        )

        measurements = cursor.fetchall()

        latest = measurements[0] if measurements else None
        previous = measurements[1] if len(measurements) > 1 else None

        return render_template(
            "temperature_tracking.html",
            measurements=measurements,
            latest=latest,
            previous=previous,
            max_datetime=datetime.now().strftime("%Y-%m-%dT%H:%M")
        )

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Temperature tracking database error")
        return "Temperature records are temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@app.route("/health-manager/temperature/delete/<int:measurement_id>", methods=["POST"])
@patient_required
def delete_temperature(measurement_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT patient_id FROM patients WHERE user_id = %s",
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        patient_id = patient[0]

        cursor.execute(
            """
            DELETE FROM health_measurements
            WHERE measurement_id = %s
              AND patient_id = %s
              AND measurement_type = 'temperature'
            """,
            (measurement_id, patient_id)
        )

        if cursor.rowcount > 0:
            connection.commit()
            flash("Temperature record deleted successfully.")
        else:
            flash("Record not found or you don't have permission to delete it.")

    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Temperature deletion error")
        flash("Unable to delete the temperature record. Please try again.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return redirect(url_for("temperature_tracking"))


@app.route("/health-manager/history/pdf")
@patient_required
def download_health_history_pdf():
    connection = None
    cursor = None
    temporary_path = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Identify the logged-in patient
        cursor.execute(
            """
            SELECT patient_id, full_name, global_pid, date_of_birth
            FROM patients
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )

        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        # 2. Fetch ALL health measurements belonging to this patient
        cursor.execute(
            """
            SELECT
                measurement_type,
                value,
                secondary_value,
                unit,
                context,
                recorded_at,
                ended_at,
                awake_minutes
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type IN (
                  'blood_sugar_fasting',
                  'blood_sugar_post_meal',
                  'blood_sugar_random',
                  'blood_sugar_hba1c',
                  'blood_pressure',
                  'heart_rate',
                  'weight',
                  'sleep_duration',
                  'temperature'
              )
            ORDER BY recorded_at ASC, uploaded_at ASC
            """,
            (patient["patient_id"],)
        )

        records = cursor.fetchall()

        # 3. Organize records for the PDF generator
        measurements = {
            "blood_sugar": [],
            "blood_pressure": [],
            "heart_rate": [],
            "weight": [],
            "sleep": [],
            "temperature": []
        }

        measurement_key = {
            "blood_sugar_fasting": "blood_sugar",
            "blood_sugar_post_meal": "blood_sugar",
            "blood_sugar_random": "blood_sugar",
            "blood_sugar_hba1c": "blood_sugar",
            "blood_pressure": "blood_pressure",
            "heart_rate": "heart_rate",
            "weight": "weight",
            "sleep_duration": "sleep",
            "temperature": "temperature"
        }

        for record in records:
            key = measurement_key.get(record["measurement_type"])

            if key:
                measurements[key].append(record)

        # 4. Prepare temporary PDF file
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name

        # 5. Generate PDF using actual database records
        patient["generated_at"] = datetime.now().strftime(
            "%d-%m-%Y %H:%M"
        )

        generate_health_history_pdf(
            temporary_path,
            patient,
            measurements
        )

        # 6. Deliver PDF (Direct download or Email)
        delivery_method = (
            request.args.get("delivery")
            or request.args.get("delivery_method")
            or "download"
        ).strip().lower()

        if delivery_method == "email":
            cursor.execute(
                "SELECT email FROM users WHERE user_id = %s",
                (session["user_id"],)
            )
            user_account = cursor.fetchone()
            patient_email = (user_account.get("email") or "").strip() if user_account else ""

            if not patient_email:
                flash("No registered email address found for your account.")
                return redirect(url_for("health_manager"))

            success, send_msg = send_health_report_email(
                patient_email,
                patient.get("full_name", "Patient"),
                temporary_path,
                report_period="All Time"
            )

            if success:
                flash(f"Your Complete Health History has been securely emailed to {patient_email}!")
            else:
                flash(f"Report generated, but email delivery encountered an issue: {send_msg}")

            return redirect(url_for("health_manager"))

        # Default: Browser download
        pdf_response = send_file(
            temporary_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="MediTrust_Health_History.pdf",
            max_age=0
        )

        # Remove temporary file after the response is closed
        pdf_response.call_on_close(
            lambda path=temporary_path: (
                os.remove(path) if os.path.exists(path) else None
            )
        )

        temporary_path = None

        return pdf_response

    except mysql.connector.Error:
        app.logger.exception("Health history database error")
        return "Unable to fetch health history. Please try again.", 503

    except Exception:
        app.logger.exception("Health history PDF generation error")
        return "Unable to generate the health history PDF.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


@app.route("/health-manager/custom-report/pdf", methods=["GET", "POST"])
@patient_required
def download_custom_health_report_pdf():
    connection = None
    cursor = None
    temporary_path = None

    try:
        # 1. Supported categories whitelist
        CATEGORY_TYPES = {
            "blood_sugar": [
                "blood_sugar_fasting",
                "blood_sugar_post_meal",
                "blood_sugar_random",
                "blood_sugar_hba1c"
            ],
            "blood_pressure": ["blood_pressure"],
            "heart_rate": ["heart_rate"],
            "weight": ["weight"],
            "sleep": ["sleep_duration"],
            "temperature": ["temperature"]
        }

        # Check POST form first, then GET query parameters
        submitted_categories = request.form.getlist("categories") or request.args.getlist("categories")

        # Filter strictly against whitelist
        selected_categories = [
            cat.strip().lower()
            for cat in submitted_categories
            if cat.strip().lower() in CATEGORY_TYPES
        ]

        # If user selected none, alert and redirect
        if not selected_categories:
            flash("Please select at least one health category to generate the report.")
            return redirect(url_for("health_manager"))

        # 2. Parse date range
        date_range_preset = (
            request.form.get("date_range")
            or request.args.get("date_range")
            or "last_30_days"
        ).strip().lower()

        now = datetime.now()
        start_datetime = None
        end_datetime = None
        date_range_label = "Last 30 Days"

        if date_range_preset == "last_7_days":
            start_datetime = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = now
            date_range_label = "Last 7 Days"

        elif date_range_preset == "last_15_days":
            start_datetime = (now - timedelta(days=15)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = now
            date_range_label = "Last 15 Days"

        elif date_range_preset == "last_30_days":
            start_datetime = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = now
            date_range_label = "Last 30 Days"

        elif date_range_preset == "last_3_months":
            start_datetime = (now - timedelta(days=90)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = now
            date_range_label = "Last 3 Months"

        elif date_range_preset == "all_time":
            start_datetime = None
            end_datetime = None
            date_range_label = "All Recorded History"

        elif date_range_preset == "custom":
            start_str = (
                request.form.get("start_date")
                or request.args.get("start_date")
                or ""
            ).strip()
            end_str = (
                request.form.get("end_date")
                or request.args.get("end_date")
                or ""
            ).strip()

            if not start_str or not end_str:
                flash("Please provide both start and end dates for a custom date range.")
                return redirect(url_for("health_manager"))

            try:
                start_datetime = datetime.strptime(start_str, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_datetime = datetime.strptime(end_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.")
                return redirect(url_for("health_manager"))

            if start_datetime > end_datetime:
                flash("Start date cannot be later than end date.")
                return redirect(url_for("health_manager"))

            date_range_label = f"{start_datetime.strftime('%d-%m-%Y')} to {end_datetime.strftime('%d-%m-%Y')}"

        else:
            start_datetime = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = now
            date_range_label = "Last 30 Days"

        # 3. Connect to database and identify authenticated patient
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT patient_id, full_name, global_pid, date_of_birth
            FROM patients
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )
        patient = cursor.fetchone()

        if patient is None:
            return "Patient profile not found.", 404

        # 4. Build query for selected categories and date range
        selected_types = []
        for cat in selected_categories:
            selected_types.extend(CATEGORY_TYPES[cat])

        placeholders = ", ".join(["%s"] * len(selected_types))
        query = f"""
            SELECT
                measurement_type,
                value,
                secondary_value,
                unit,
                context,
                recorded_at,
                ended_at,
                awake_minutes
            FROM health_measurements
            WHERE patient_id = %s
              AND measurement_type IN ({placeholders})
        """
        params = [patient["patient_id"]] + selected_types

        if start_datetime and end_datetime:
            query += " AND recorded_at >= %s AND recorded_at <= %s"
            params.extend([start_datetime, end_datetime])

        query += " ORDER BY recorded_at ASC, uploaded_at ASC"

        cursor.execute(query, tuple(params))
        records = cursor.fetchall()

        # 5. Organize records for PDF generator
        measurements = {
            "blood_sugar": [],
            "blood_pressure": [],
            "heart_rate": [],
            "weight": [],
            "sleep": [],
            "temperature": []
        }

        measurement_key_map = {
            "blood_sugar_fasting": "blood_sugar",
            "blood_sugar_post_meal": "blood_sugar",
            "blood_sugar_random": "blood_sugar",
            "blood_sugar_hba1c": "blood_sugar",
            "blood_pressure": "blood_pressure",
            "heart_rate": "heart_rate",
            "weight": "weight",
            "sleep_duration": "sleep",
            "temperature": "temperature"
        }

        for record in records:
            key = measurement_key_map.get(record["measurement_type"])
            if key and key in measurements:
                measurements[key].append(record)

        # 6. Prepare temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_path = temporary_file.name

        # 7. Generate PDF
        patient["generated_at"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        patient["date_range_label"] = date_range_label

        generate_health_history_pdf(
            temporary_path,
            patient,
            measurements,
            selected_categories=selected_categories,
            date_range_label=date_range_label
        )

        # 8. Deliver PDF (Direct download or Email to registered address)
        delivery_method = (
            request.form.get("delivery_method")
            or request.args.get("delivery_method")
            or "download"
        ).strip().lower()

        if delivery_method == "email":
            cursor.execute(
                "SELECT email FROM users WHERE user_id = %s",
                (session["user_id"],)
            )
            user_account = cursor.fetchone()
            patient_email = (user_account.get("email") or "").strip() if user_account else ""

            if not patient_email:
                flash("No registered email address found for your account.")
                return redirect(url_for("health_manager"))

            success, send_msg = send_health_report_email(
                patient_email,
                patient.get("full_name", "Patient"),
                temporary_path,
                report_period=date_range_label
            )

            if success:
                flash(f"Your Health Report has been securely emailed to {patient_email}!")
            else:
                flash(f"Report generated, but email delivery encountered an issue: {send_msg}")

            return redirect(url_for("health_manager"))

        # Default: Browser download
        pdf_response = send_file(
            temporary_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="MediTrust_Custom_Health_Report.pdf",
            max_age=0
        )

        pdf_response.call_on_close(
            lambda path=temporary_path: (
                os.remove(path) if os.path.exists(path) else None
            )
        )

        temporary_path = None
        return pdf_response

    except mysql.connector.Error:
        app.logger.exception("Custom health report database error")
        return "Unable to fetch health records. Please try again.", 503

    except Exception:
        app.logger.exception("Custom health report PDF generation error")
        return "Unable to generate the custom health report PDF.", 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


@app.route("/my-analyses")
@patient_required
def my_analyses():
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

        return render_template(
            "my_analyses.html",
            analyses=analyses,
        )

    except mysql.connector.Error:
        app.logger.exception(
            "Database error loading patient analysis history"
        )
        return (
            "Analysis history is temporarily unavailable. "
            "Please try again later.",
            503,
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
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


        try:
            if isinstance(analysis["extracted_data"], str):
                analysis["extracted_data"] = json.loads(
                    analysis["extracted_data"]
                )
        except (json.JSONDecodeError, TypeError):
            app.logger.warning(
                "Invalid extracted JSON for analysis ID %s",
                analysis_id,
            )
            analysis["extracted_data"] = None

        # Parse findings independently of extracted_data
        try:
            if isinstance(analysis["findings"], str):
                analysis["findings"] = json.loads(
                    analysis["findings"]
                )
        except (json.JSONDecodeError, TypeError):
            app.logger.warning(
                "Invalid findings JSON for analysis ID %s",
                analysis_id,
            )
            analysis["findings"] = None

        
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


@app.route("/api/summarize-analysis", methods=["POST"])
@patient_required
def api_summarize_analysis():
    data = request.get_json(silent=True) or {}
    analysis_id = data.get("analysis_id")
    extracted_data = data.get("extracted_data")

    connection = None
    cursor = None
    try:
        # If analysis_id provided, fetch extracted_data from database
        if analysis_id:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT a.extracted_data
                FROM analysis_results a
                JOIN medical_documents d ON a.document_id = d.document_id
                JOIN patients p ON d.patient_id = p.patient_id
                WHERE a.analysis_id = %s AND p.user_id = %s
                LIMIT 1
                """,
                (analysis_id, session["user_id"])
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"success": False, "error": "Analysis record not found."}), 404

            raw_extracted = row["extracted_data"]
            if isinstance(raw_extracted, str):
                extracted_data = json.loads(raw_extracted)
            else:
                extracted_data = raw_extracted

        if not extracted_data:
            return jsonify({"success": False, "error": "No extracted report data available to summarize."}), 400

        # Generate summary using Gemini
        summary = summarize_medical_report(extracted_data)
        return jsonify({"success": True, "summary": summary})

    except Exception as exc:
        app.logger.exception("AI summarization error")
        return jsonify({"success": False, "error": f"Summarization failed: {str(exc)}"}), 500
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _fetch_patient_measurements_for_category(connection, patient_id, category, limit=15):
    cursor = connection.cursor(dictionary=True)
    try:
        cat = (category or "").lower()
        if "pressure" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type = 'blood_pressure'
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        elif "sugar" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type IN ('blood_sugar_fasting', 'blood_sugar_post_meal', 'blood_sugar_random', 'blood_sugar_hba1c')
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        elif "heart" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type = 'heart_rate'
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        elif "weight" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type = 'weight'
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        elif "sleep" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at, awake_minutes
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type = 'sleep_duration'
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        elif "temp" in cat:
            query = """
                SELECT measurement_id, measurement_type, value, secondary_value, unit, context, recorded_at
                FROM health_measurements
                WHERE patient_id = %s AND measurement_type = 'temperature'
                ORDER BY recorded_at DESC, uploaded_at DESC
                LIMIT %s
            """
            params = (patient_id, limit)
        else:
            return []

        cursor.execute(query, params)
        rows = cursor.fetchall()
        for r in rows:
            if isinstance(r.get("recorded_at"), (datetime, date)):
                r["recorded_at"] = r["recorded_at"].strftime("%Y-%m-%d %H:%M")
        return rows
    finally:
        cursor.close()


@app.route("/api/health-insights/generate", methods=["POST"])
@patient_required
def api_generate_health_insight():
    data = request.get_json(silent=True) or {}
    category = data.get("category", "blood_pressure")

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT patient_id FROM patients WHERE user_id = %s", (session["user_id"],))
        patient = cursor.fetchone()
        cursor.close()

        if not patient:
            return jsonify({"success": False, "error": "Patient profile not found."}), 404

        patient_id = patient["patient_id"]
        rows = _fetch_patient_measurements_for_category(connection, patient_id, category, limit=15)

        if not rows:
            return jsonify({
                "success": False,
                "error": "No recorded measurements found for this category. Log your first reading above!"
            }), 200

        latest = rows[0]
        history = rows[1:] if len(rows) > 1 else []

        insight = generate_measurement_insight(category, latest, history)

        return jsonify({
            "success": True,
            "category": category,
            "insight": insight,
            "latest": latest,
            "history_count": len(history)
        })
    except Exception as exc:
        app.logger.exception("Error generating health insight")
        return jsonify({"success": False, "error": f"Failed to generate insight: {str(exc)}"}), 500
    finally:
        if connection is not None:
            connection.close()


@app.route("/api/health-insights/ask", methods=["POST"])
@patient_required
def api_ask_health_insight():
    data = request.get_json(silent=True) or {}
    category = data.get("category", "blood_pressure")
    question = (data.get("question") or "").strip()
    previous_insight = (data.get("previous_insight") or "").strip()

    if not question:
        return jsonify({"success": False, "error": "Please provide a question."}), 400

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT patient_id FROM patients WHERE user_id = %s", (session["user_id"],))
        patient = cursor.fetchone()
        cursor.close()

        if not patient:
            return jsonify({"success": False, "error": "Patient profile not found."}), 404

        patient_id = patient["patient_id"]
        rows = _fetch_patient_measurements_for_category(connection, patient_id, category, limit=15)
        latest = rows[0] if rows else None
        history = rows[1:] if len(rows) > 1 else []

        answer = answer_followup_question(category, latest, history, previous_insight, question)

        return jsonify({
            "success": True,
            "answer": answer
        })
    except Exception as exc:
        app.logger.exception("Error answering health question")
        return jsonify({"success": False, "error": f"Failed to answer question: {str(exc)}"}), 500
    finally:
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




@app.route("/hospital-access-request/<int:request_id>/document")
@login_required
def view_authorized_document(request_id):
    if session.get("role") != "hospital":
        return "Forbidden: hospital account required.", 403

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT d.stored_file_name
            FROM access_requests AS ar
            JOIN medical_documents AS d
                ON d.document_id = ar.document_id
            JOIN users AS u
                ON u.hospital_id = ar.hospital_id
            WHERE ar.request_id = %s
              AND u.user_id = %s
              AND u.role = 'hospital'
              AND u.is_active = 1
              AND ar.status = 'approved'
              AND ar.expires_at > CURRENT_TIMESTAMP
            LIMIT 1
            """,
            (request_id, session["user_id"]),
        )

        document = cursor.fetchone()

        if document is None:
            return (
                "Document access denied. The request may be unapproved, "
                "expired, or not assigned to your hospital.",
                403,
            )

        stored_file_name = document["stored_file_name"]

    except mysql.connector.Error:
        app.logger.exception("Failed to authorize document viewing")
        return "Document access is temporarily unavailable.", 503

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    # Only generated filenames are accepted; never use a user-supplied path.
    if (
        not stored_file_name
        or os.path.basename(stored_file_name) != stored_file_name
        or not stored_file_name.endswith(".pdf")
    ):
        return "Stored document reference is invalid.", 404

    private_file_path = os.path.join(
        PRIVATE_UPLOAD_DIR, stored_file_name
    )

    if not os.path.isfile(private_file_path):
        return "The original PDF is not available in private storage.", 404

    return send_file(
        private_file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name="medical_report.pdf",
        conditional=True,
        max_age=0,
    )


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

    safe_name = secure_filename(uploaded_file.filename)
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        flash("Only PDF files are allowed.")
        return redirect(url_for("verify_document"))

    uploaded_file.stream.seek(0)
    signature = uploaded_file.stream.read(5)
    uploaded_file.stream.seek(0)

    if signature != b"%PDF-":
        flash("The selected file does not appear to be a valid PDF.")
        return redirect(url_for("verify_document"))

    temporary_path = None
    private_file_path = None
    connection = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pdf", delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
            uploaded_file.save(temporary_path)

        # Analyze the original PDF before moving it.
        result = run_analysis(temporary_path)

        connection = get_connection()
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

        extracted_data = result.get("extracted_data", {})
        report_number = extracted_data.get("report_number")
        report_date = parse_report_date(
            extracted_data.get("report_date")
        )

        internal_reference = generate_internal_reference()
        stored_file_name = f"{uuid.uuid4().hex}.pdf"
        private_file_path = os.path.join(
            PRIVATE_UPLOAD_DIR, stored_file_name
        )
        file_sha256 = calculate_file_sha256(temporary_path)

        # Move the PDF to private storage before recording its filename.
        os.replace(temporary_path, private_file_path)
        temporary_path = None

        try:
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

        except Exception:
            connection.rollback()

            # Remove the PDF when the database save fails.
            if os.path.exists(private_file_path):
                try:
                    os.remove(private_file_path)
                except OSError:
                    app.logger.exception(
                        "Could not remove PDF after database failure"
                    )
            raise

        result["internal_reference"] = internal_reference
        result["document_id"] = save_result["document_id"]
        result["analysis_id"] = save_result["analysis_id"]

        return render_template(
            "analysis_result.html",
            result=result,
            original_filename=safe_name,
        )

    except Exception:
        app.logger.exception("Medical document analysis failed")
        flash("Analysis could not be completed. Please try again.")
        return redirect(url_for("verify_document"))

    finally:
        if connection is not None:
            connection.close()

        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                app.logger.exception(
                    "Could not remove temporary upload"
                )


if __name__ == "__main__":
    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "Add FLASK_SECRET_KEY to your .env file before starting MediTrust."
        )

    # Local development only. Do not expose the debug server publicly.
    app.run(debug=True)
