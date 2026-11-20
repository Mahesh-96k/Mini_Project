
import os

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )


def register_demo_patient(full_name, username, password, hospital_id):
    full_name = full_name.strip()
    username = username.strip()
    hospital_id = hospital_id.strip().upper()

    if not full_name:
        raise ValueError("Patient name is required.")

    if len(full_name) > 150:
        raise ValueError("Patient name must be 150 characters or fewer.")

    if not username:
        raise ValueError("Username is required.")

    if len(username) > 100:
        raise ValueError("Username must be 100 characters or fewer.")

    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    if not hospital_id:
        raise ValueError("Hospital ID is required.")

    password_hash = generate_password_hash(password)

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()
        connection.start_transaction()

        # Confirm this is a demo hospital in our registry.
        cursor.execute(
            """
            SELECT hospital_id
            FROM hospitals
            WHERE hospital_id = %s
              AND is_demo = TRUE
              AND is_approved = FALSE
            FOR UPDATE
            """,
            (hospital_id,),
        )

        if cursor.fetchone() is None:
            raise ValueError(
                "Demo hospital not found. Check the hospital ID."
            )

        # Create the patient login with a securely hashed password.
        cursor.execute(
            """
            INSERT INTO users
                (username, password_hash, role, hospital_id)
            VALUES (%s, %s, 'patient', NULL)
            """,
            (username, password_hash),
        )

        user_id = cursor.lastrowid

        # Insert a temporary unique PID, then replace it after
        # MySQL assigns the internal patient ID.
        cursor.execute(
            """
            INSERT INTO patients (global_pid, full_name, user_id)
            VALUES (%s, %s, %s)
            """,
            (f"PENDING-{user_id}", full_name, user_id),
        )

        patient_id = cursor.lastrowid

        # Keep the public PID separate from the internal database ID.
        # The first patient gets PI100, the second PI101, and so on.
        global_pid = f"PI{patient_id + 99:03d}"

        cursor.execute(
            """
            UPDATE patients
            SET global_pid = %s
            WHERE patient_id = %s
            """,
            (global_pid, patient_id),
        )

        # Create the hospital counter if it does not exist.
        cursor.execute(
            """
            INSERT INTO hospital_id_counters
                (hospital_id, next_sequence)
            VALUES (%s, 1)
            ON DUPLICATE KEY UPDATE
                next_sequence = next_sequence
            """,
            (hospital_id,),
        )

        # Lock this hospital's counter row during allocation.
        cursor.execute(
            """
            SELECT next_sequence
            FROM hospital_id_counters
            WHERE hospital_id = %s
            FOR UPDATE
            """,
            (hospital_id,),
        )

        sequence = cursor.fetchone()[0]

        hpid = f"{global_pid}-{hospital_id}-{sequence:03d}"

        cursor.execute(
            """
            UPDATE hospital_id_counters
            SET next_sequence = %s
            WHERE hospital_id = %s
            """,
            (sequence + 1, hospital_id),
        )

        cursor.execute(
            """
            INSERT INTO hospital_patient_links
                (patient_id, hospital_id, hpid)
            VALUES (%s, %s, %s)
            """,
            (patient_id, hospital_id, hpid),
        )

        connection.commit()

        return {
            "patient_id": patient_id,
            "global_pid": global_pid,
            "hospital_id": hospital_id,
            "hpid": hpid,
        }

    except Exception:
        if connection is not None:
            connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()
