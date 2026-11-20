
import os
import hashlib
import json
from datetime import date
from dotenv import load_dotenv
import mysql.connector

from analysis_storage import save_analysis_result

load_dotenv()

TEST_REPORT_NUMBER = "MT-STORE-TEST-001"

connection = None

try:
    connection = mysql.connector.connect(

        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )
    print("Python database:", connection.database)
    print("Python server:", connection.server_host)
    print("Python port:", connection.server_port)
    cursor_check = connection.cursor()
    cursor_check.execute(
        "SELECT DATABASE(), @@hostname, @@port, CONNECTION_ID()"
    )
    print("Python connection identity:", cursor_check.fetchone())
    cursor_check.close()

    connection.start_transaction()
    cursor_check = connection.cursor()
    cursor_check.execute("SELECT COUNT(*) FROM medical_documents")
    print("Python total documents:", cursor_check.fetchone())

    cursor_check.execute(
        """
        SELECT document_id, report_number
        FROM medical_documents
        WHERE report_number = %s
        """,
        (TEST_REPORT_NUMBER,),
    )
    print("Python matching report:", cursor_check.fetchall())
    cursor_check.close()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT p.patient_id, p.user_id
        FROM patients p
        WHERE p.patient_id = %s
        """,
        (1,),
    )
    patient = cursor.fetchone()

    if patient is None:
        raise RuntimeError("Synthetic test patient was not found.")

    cursor.execute(
        """
        SELECT hospital_id, is_demo
        FROM hospitals
        WHERE hospital_id = %s
        """,
        ("KRD",),
    )
    hospital = cursor.fetchone()

    if hospital is None or not hospital["is_demo"]:
        raise RuntimeError("Expected demo hospital was not found.")

    cursor.execute(
        """
        SELECT document_id
        FROM medical_documents
        WHERE hospital_id = %s AND report_number = %s
        """,
        ("KRD", TEST_REPORT_NUMBER),
    )

    existing_record = cursor.fetchone()
    print("Existing test record:", existing_record)

    if existing_record:
        cursor.execute(
            """
            SELECT
                document_id,
                hospital_id,
                report_number,
                document_type,
                stored_file_name,
                patient_id,
                uploaded_by
            FROM medical_documents
            WHERE document_id = %s
            """,
            (existing_record["document_id"],),
        )

        print("Full matching record:", cursor.fetchone())
        raise RuntimeError("Test report already exists; stopping safely.")

    # Synthetic metadata only; no PDF is claimed to be stored.
    fake_hash = hashlib.sha256(
        b"MediTrust synthetic rollback-only test"
    ).hexdigest()

    cursor.execute(
        """
        INSERT INTO medical_documents (
            patient_id, hospital_id, report_number, document_type,
            report_date, stored_file_name, file_sha256, uploaded_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            patient["patient_id"],
            hospital["hospital_id"],
            TEST_REPORT_NUMBER,
            "SYNTHETIC_TEST_ONLY",
            date(2026, 10, 15),
            "SYNTHETIC_ROLLBACK_ONLY.pdf",
            fake_hash,
            patient["user_id"],
        ),
    )

    document_id = cursor.lastrowid
    cursor.close()

    fake_result = {
        "extracted_data": {
            "patient_name": "Fictional Test Patient",
            "patient_id": "TEST-P001",
            "hospital_name": "Synthetic Demo Hospital",
            "report_number": TEST_REPORT_NUMBER,
            "report_date": "2026-10-15",
            "doctor_name": "Dr. Demo",
            "test_name": "Hemoglobin",
            "test_result": "14.2 g/dL",
            "missing_fields": [],
        },
        "fraud_analysis": {
            "risk_score": 0,
            "risk_level": "Low",
            "review_status": "no_configured_flags",
            "findings": [],
        },
    }

    analysis_id = save_analysis_result(
        connection, document_id, fake_result
    )

    print("Both inserts succeeded inside the transaction.")
    print("Synthetic document ID:", document_id)
    print("Synthetic analysis ID:", analysis_id)
    print("Rolling back test data now.")




    connection.rollback()

    verify_cursor = connection.cursor(dictionary=True)

    verify_cursor.execute(
        """
        SELECT document_id
        FROM medical_documents
        WHERE hospital_id = %s
         AND report_number = %s
        AND document_type = %s
        AND stored_file_name = %s
        """,
        (
        "KRD",
        TEST_REPORT_NUMBER,
        "SYNTHETIC_TEST_ONLY",
        "SYNTHETIC_ROLLBACK_ONLY.pdf",
        ),
    )

    remaining_document = verify_cursor.fetchone()

    verify_cursor.execute(
        """
        SELECT analysis_id
        FROM analysis_results
        WHERE JSON_UNQUOTE(
            JSON_EXTRACT(extracted_data, '$.report_number')
        ) = %s
        """,
        (TEST_REPORT_NUMBER,),
    )

    remaining_analysis = verify_cursor.fetchone()
    verify_cursor.close()

    if remaining_document is None and remaining_analysis is None:
        print("PASS: Both synthetic test records were rolled back.")
    else:
        raise RuntimeError(
            "Rollback verification failed. Check the test records before continuing."
        )
    






except Exception as error:
    if connection is not None:
        connection.rollback()
    print("Rollback-only test failed:", error)

finally:
    if connection is not None:
        connection.close()
