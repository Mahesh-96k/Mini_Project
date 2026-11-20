
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

schema_path = Path(__file__).parent / "schema.sql"

if not schema_path.exists():
    raise FileNotFoundError("schema.sql was not found.")

schema = schema_path.read_text(encoding="utf-8")

statements = [
    statement.strip()
    for statement in schema.split(";")
    if statement.strip()
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

    for statement in statements:
        cursor.execute(statement)

    connection.commit()

    print("MediTrust database schema created successfully!")
    print(f"Database: {os.getenv('MYSQL_DATABASE')}")
    print(f"Tables processed: {len(statements)}")

except mysql.connector.Error as error:
    print("Database setup failed:", error)
    raise

finally:
    if cursor is not None:
        cursor.close()
    if connection is not None and connection.is_connected():
        connection.close()

