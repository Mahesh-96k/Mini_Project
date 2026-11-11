
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
)

try:
    cursor = connection.cursor()

    cursor.execute("SHOW COLUMNS FROM patients")
    print("PATIENTS TABLE")
    for row in cursor.fetchall():
        print(row[0], "-", row[1], "| Key:", row[3])

    cursor.execute("SHOW COLUMNS FROM hospital_patient_links")
    print("\nHOSPITAL PATIENT LINKS TABLE")
    for row in cursor.fetchall():
        print(row[0], "-", row[1], "| Key:", row[3])

finally:
    cursor.close()
    connection.close()
