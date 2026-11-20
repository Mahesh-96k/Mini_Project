import os
import smtplib
import secrets
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import logging
from dotenv import load_dotenv

logger = logging.getLogger("meditrust.email")


def generate_and_store_otp(connection, user_id, purpose="login", validity_minutes=5):
    """
    Generate a secure 6-digit OTP and store it in email_otps table.
    Invalidates any previous pending OTPs for this user and purpose.
    """
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now() + timedelta(minutes=validity_minutes)

    cursor = connection.cursor(dictionary=True)
    try:
        # Invalidate existing unused OTPs for this user and purpose
        cursor.execute(
            """
            UPDATE email_otps
            SET is_used = 1
            WHERE user_id = %s AND purpose = %s AND is_used = 0
            """,
            (user_id, purpose)
        )

        # Insert new OTP
        cursor.execute(
            """
            INSERT INTO email_otps (user_id, otp_code, purpose, expires_at, is_used)
            VALUES (%s, %s, %s, %s, 0)
            """,
            (user_id, otp_code, purpose, expires_at)
        )
        connection.commit()
        return otp_code
    finally:
        cursor.close()


def verify_otp(connection, user_id, submitted_code, purpose="login"):
    """
    Verify if the submitted OTP is valid, unused, and not expired.
    If valid, marks it as used.
    """
    if not submitted_code:
        return False, "OTP code is required."

    submitted_code = str(submitted_code).strip()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT otp_id, otp_code, expires_at, is_used
            FROM email_otps
            WHERE user_id = %s AND purpose = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, purpose)
        )
        record = cursor.fetchone()

        if not record:
            return False, "No OTP request found. Please request a new code."

        if record["is_used"]:
            return False, "This OTP has already been used. Please request a new one."

        if datetime.now() > record["expires_at"]:
            return False, "This OTP has expired. Please request a new one."

        if record["otp_code"] != submitted_code:
            return False, "Incorrect OTP code. Please try again."

        # Mark OTP as used
        cursor.execute(
            "UPDATE email_otps SET is_used = 1 WHERE otp_id = %s",
            (record["otp_id"],)
        )
        connection.commit()
        return True, "Verification successful."
    finally:
        cursor.close()


def send_email(to_email, subject, body_html, body_text=None, attachment_path=None, attachment_filename=None):
    """
    Sends an email via SMTP.
    If SMTP credentials are not configured in environment, falls back
    to safe demo/console logging so testing is never blocked.
    """
    # Ensure latest .env values are loaded even if server wasn't restarted
    load_dotenv(override=True)

    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    sender_email = os.getenv("MAIL_DEFAULT_SENDER", mail_username or "noreply@meditrust.local")

    # If no SMTP credentials provided, run in DEMO MODE (log to terminal)
    if not mail_username or not mail_password:
        print("\n" + "=" * 65)
        print(" [MEDITRUST EMAIL SERVICE - DEMO / DEVELOPMENT MODE]")
        print(f" To: {to_email}")
        print(f" Subject: {subject}")
        if attachment_path:
            print(f" Attachment: {attachment_filename or os.path.basename(attachment_path)}")
        print("-" * 65)
        print(body_text or body_html)
        print("=" * 65 + "\n")
        return True, "Email simulated in Demo Mode (logged to terminal)."

    # Real SMTP delivery
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"MediTrust Healthcare <{sender_email}>"
        msg["To"] = to_email

        alt_part = MIMEMultipart("alternative")
        if body_text:
            alt_part.attach(MIMEText(body_text, "plain"))
        alt_part.attach(MIMEText(body_html, "html"))
        msg.attach(alt_part)

        # Attach file if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as file_handle:
                attachment = MIMEApplication(file_handle.read(), _subtype="pdf")
                filename = attachment_filename or os.path.basename(attachment_path)
                attachment.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(attachment)

        with smtplib.SMTP(mail_server, mail_port) as server:
            server.ehlo()
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)

        return True, "Email sent successfully."

    except Exception as exc:
        logger.exception("Failed to send email via SMTP")
        print(f"\n[EMAIL SMTP ERROR]: {exc}")
        print(f"[DEMO FALLBACK for {to_email}]: Subject: {subject}")
        return False, f"Failed to send email: {exc}"


def send_otp_email(to_email, otp_code, username="Patient"):
    """
    Format and send a branded 2FA verification email with the 6-digit OTP.
    """
    subject = f"Your MediTrust Security Code: {otp_code}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }}
            .header {{ background-color: #087E75; padding: 24px; text-align: center; color: #ffffff; }}
            .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
            .content {{ padding: 30px 25px; color: #334155; line-height: 1.6; }}
            .otp-box {{ background: #f0fdfa; border: 2px dashed #087E75; border-radius: 10px; padding: 18px; text-align: center; margin: 25px 0; }}
            .otp-code {{ font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #087E75; font-family: monospace; }}
            .notice {{ font-size: 13px; color: #64748b; margin-top: 20px; }}
            .footer {{ background: #f1f5f9; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>MediTrust Healthcare</h1>
                <p style="margin: 5px 0 0; font-size: 13px; opacity: 0.9;">Secure Patient Portal Authentication</p>
            </div>
            <div class="content">
                <p>Hello <strong>{username}</strong>,</p>
                <p>We received a sign-in request for your MediTrust account. To complete the two-step verification, use the one-time security code below:</p>
                
                <div class="otp-box">
                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #0f766e; margin-bottom: 6px; font-weight: 600;">One-Time Verification Code</div>
                    <div class="otp-code">{otp_code}</div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 6px;">Valid for 5 minutes</div>
                </div>

                <p class="notice">
                    🔒 <strong>Security Tip:</strong> Never share this code with anyone. MediTrust staff will never ask for your verification code. If you did not initiate this login, please secure your account immediately.
                </p>
            </div>
            <div class="footer">
                © 2026 MediTrust Healthcare Information Management System.<br>
                This is an automated security notification.
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"Hello {username},\n\nYour MediTrust 2-Step Verification Code is: {otp_code}\n\nThis code is valid for 5 minutes.\nIf you did not request this code, please ignore this email."

    return send_email(to_email, subject, body_html, body_text=body_text)


def send_health_report_email(to_email, patient_name, pdf_path, report_period="All Time"):
    """
    Format and send the generated Health History PDF report directly to the patient's email.
    """
    subject = f"Your MediTrust Health History Report ({report_period})"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }}
            .header {{ background-color: #087E75; padding: 24px; text-align: center; color: #ffffff; }}
            .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
            .content {{ padding: 30px 25px; color: #334155; line-height: 1.6; }}
            .badge-box {{ background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 8px; padding: 14px; margin: 20px 0; }}
            .disclaimer {{ background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 12px 14px; font-size: 12px; color: #92400e; margin-top: 20px; }}
            .footer {{ background: #f1f5f9; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>MediTrust Healthcare</h1>
                <p style="margin: 5px 0 0; font-size: 13px; opacity: 0.9;">Confidential Health Information</p>
            </div>
            <div class="content">
                <p>Dear <strong>{patient_name}</strong>,</p>
                <p>As requested from your Personal Health Manager portal, your official Health History Report is attached to this email as a secure PDF document.</p>
                
                <div class="badge-box">
                    <div style="font-size: 13px; font-weight: 600; color: #0f766e;">Report Details:</div>
                    <ul style="margin: 8px 0 0; padding-left: 20px; font-size: 13px; color: #1e293b;">
                        <li><strong>Patient Name:</strong> {patient_name}</li>
                        <li><strong>Report Period:</strong> {report_period}</li>
                        <li><strong>Attachment:</strong> MediTrust_Health_Report.pdf</li>
                    </ul>
                </div>

                <div class="disclaimer">
                    ⚠ <strong>Medical Disclaimer:</strong> This report is generated from health metrics recorded in MediTrust. It is intended for personal health tracking and discussion with qualified healthcare professionals. It does not replace professional medical diagnosis.
                </div>
            </div>
            <div class="footer">
                © 2026 MediTrust Healthcare Platform. Confidential medical documentation.<br>
                Sent securely to your registered patient email address.
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"Dear {patient_name},\n\nPlease find attached your MediTrust Health History Report ({report_period}).\n\nConfidential Medical Documentation."

    return send_email(
        to_email,
        subject,
        body_html,
        body_text=body_text,
        attachment_path=pdf_path,
        attachment_filename="MediTrust_Health_Report.pdf"
    )
