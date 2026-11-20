
import hashlib
import json
import uuid
from datetime import datetime


def calculate_file_sha256(file_path):
    """Calculate the SHA-256 fingerprint of a PDF."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as pdf_file:
        for chunk in iter(lambda: pdf_file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def parse_report_date(value):
    """Return a MySQL-compatible date or None."""
    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    
def generate_internal_reference():
    """Generate a unique internal MediTrust document reference."""
    return f"MT-DOC-{uuid.uuid4().hex[:12].upper()}"

def validate_analysis_result(result):
    """Validate the analysis structure before database storage."""
    if not isinstance(result, dict):
        raise ValueError("Analysis result must be a dictionary.")

    extracted_data = result.get("extracted_data")
    fraud_analysis = result.get("fraud_analysis")

    if not isinstance(extracted_data, dict):
        raise ValueError("Extracted data is missing.")

    if not isinstance(fraud_analysis, dict):
        raise ValueError("Fraud analysis is missing.")

    risk_score = fraud_analysis.get("risk_score")
    risk_level = fraud_analysis.get("risk_level")
    review_status = fraud_analysis.get("review_status")
    findings = fraud_analysis.get("findings")

    if type(risk_score) is not int or not 0 <= risk_score <= 100:
        raise ValueError("Risk score must be an integer from 0 to 100.")

    if risk_level not in ("Low", "Medium", "High"):
        raise ValueError("Invalid risk level.")

    if not isinstance(review_status, str) or not review_status.strip():
        raise ValueError("Review status is missing.")

    if not isinstance(findings, list):
        raise ValueError("Findings must be a list.")

    # Ensure values can be serialized to MySQL JSON columns.
    extracted_json = json.dumps(extracted_data, ensure_ascii=False)
    findings_json = json.dumps(findings, ensure_ascii=False)

    return {
        "extracted_json": extracted_json,
        "findings_json": findings_json,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "review_status": review_status,
        "report_number": extracted_data.get("report_number"),
        "report_date": parse_report_date(
            extracted_data.get("report_date")
        ),
    }



def save_analysis_result(connection, document_id, result):
    """Save analysis output for an existing document record."""
    prepared = validate_analysis_result(result)

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO analysis_results (
                document_id,
                extracted_data,
                risk_score,
                risk_level,
                review_status,
                findings
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                document_id,
                prepared["extracted_json"],
                prepared["risk_score"],
                prepared["risk_level"],
                prepared["review_status"],
                prepared["findings_json"],
            ),
        )

        analysis_id = cursor.lastrowid
        return analysis_id

    

    finally:
        cursor.close()


def save_document_analysis(
    connection,
    patient_id,
    hospital_id,
    internal_reference,
    uploaded_by,
    report_number,
    document_type,
    report_date,
    stored_file_name,
    file_sha256,
    result,
):
    """Save document metadata and analysis within the caller's transaction."""
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO medical_documents (
                patient_id,
                hospital_id,
                internal_reference,
                report_number,
                document_type,
                report_date,
                stored_file_name,
                file_sha256,
                uploaded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                hospital_id,
                internal_reference,
                report_number,
                document_type,
                report_date,
                stored_file_name,
                file_sha256,
                uploaded_by,
            ),
        )

        document_id = cursor.lastrowid

        analysis_id = save_analysis_result(
            connection,
            document_id,
            result,
        )

        return {
            "document_id": document_id,
            "analysis_id": analysis_id,
        }

    finally:
        cursor.close()
