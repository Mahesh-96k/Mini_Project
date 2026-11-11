
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

connection = None

try:
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )

    print("MediTrust database connection successful!")
    print("Connected database:", connection.database)

except mysql.connector.Error as error:
    print("Database connection failed:", error)

finally:
    if connection and connection.is_connected():
        connection.close()
