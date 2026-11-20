
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

hospitals = [
    ("KRD", "Kerudi Multispecialty Hospital"),
    ("DNR", "Daddenavar Hospital"),
    ("HSK", "HSK Hospital"),
    ("DGH", "District Government Hospital"),
    ("ASK", "ASKI Hospital"),
]

connection = None
cursor = None

try:
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )

    cursor = connection.cursor()

    query = """
        INSERT INTO hospitals (
            hospital_id,
            hospital_name,
            city,
            district,
            state,
            is_demo,
            is_approved
        )
        VALUES (%s, %s, %s, %s, %s, TRUE, FALSE)
        ON DUPLICATE KEY UPDATE
            hospital_name = VALUES(hospital_name),
            city = VALUES(city),
            district = VALUES(district),
            state = VALUES(state),
            is_demo = TRUE,
            is_approved = FALSE
    """

    for hospital_id, hospital_name in hospitals:
        cursor.execute(
            query,
            (
                hospital_id,
                hospital_name,
                "Bagalkot",
                "Bagalkot",
                "Karnataka",
            ),
        )

    connection.commit()

    cursor.execute("""
        SELECT hospital_id, hospital_name, city, is_demo, is_approved
        FROM hospitals
        ORDER BY hospital_id
    """)

    print("\nMEDITRUST DEMO HOSPITAL REGISTRY")
    print("-" * 65)

    for row in cursor.fetchall():
        print(
            f"ID: {row[0]} | Name: {row[1]} | "
            f"City: {row[2]} | Demo: {row[3]} | "
            f"Approved: {row[4]}"
        )

    print("\nHospital registry setup completed.")

except mysql.connector.Error as error:
    print("Hospital registry setup failed:", error)
    raise

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()
