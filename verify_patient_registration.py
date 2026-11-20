
from patient_registration import get_connection
from werkzeug.security import check_password_hash

connection = get_connection()
cursor = connection.cursor(dictionary=True)

try:
    cursor.execute(
        """
        SELECT
            p.patient_id,
            p.global_pid,
            p.full_name,
            hpl.hospital_id,
            hpl.hpid,
            u.username,
            u.password_hash
        FROM patients p
        JOIN users u ON u.user_id = p.user_id
        JOIN hospital_patient_links hpl
            ON hpl.patient_id = p.patient_id
        WHERE p.global_pid = %s
        """,
        ("PI100",),
    )

    patient = cursor.fetchone()

    if patient is None:
        print("Verification failed: patient not found.")
    else:
        print("Patient record found!")
        print("Name:", patient["full_name"])
        print("Global PID:", patient["global_pid"])
        print("Hospital ID:", patient["hospital_id"])
        print("HPID:", patient["hpid"])
        print("Username:", patient["username"])

        stored_hash = patient["password_hash"]

        print(
            "Password hash stored:",
            bool(stored_hash)
            and stored_hash != "NOT_A_REAL_PASSWORD_HASH",
        )

        # Check the test password locally without printing it.
        password_valid = check_password_hash(
            stored_hash,
            "MediTrustTest2026!",
        )
        print("Password hash verification:", password_valid)

finally:
    cursor.close()
    connection.close()
