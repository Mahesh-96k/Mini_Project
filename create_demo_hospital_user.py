
from getpass import getpass
from werkzeug.security import generate_password_hash
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

username = input("Choose a demo hospital username: ").strip()
password = getpass("Choose a demo password (minimum 8 characters): ")

if not username or len(password) < 8:
    raise SystemExit("Username is required and password must be at least 12 characters.")

connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
)

cursor = connection.cursor()

try:
    cursor.execute(
        """
        SELECT hospital_id
        FROM hospitals
        WHERE hospital_id = 'KRD'
          AND is_demo = TRUE
          AND is_approved = FALSE
        """
    )

    if cursor.fetchone() is None:
        raise SystemExit("Expected KRD demo hospital was not found.")

    cursor.execute(
        "SELECT user_id FROM users WHERE username = %s",
        (username,),
    )

    if cursor.fetchone() is not None:
        raise SystemExit("That username already exists. Choose another.")

    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, hospital_id)
        VALUES (%s, %s, 'hospital', 'KRD')
        """,
        (username, generate_password_hash(password)),
    )

    connection.commit()
    print("Demo hospital staff account created successfully.")
    print("Hospital ID: KRD")
    print("Username:", username)
    print("Password: not displayed or stored in plain text.")

except Exception:
    connection.rollback()
    raise

finally:
    cursor.close()
    connection.close()
