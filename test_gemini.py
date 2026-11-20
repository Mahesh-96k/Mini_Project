import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=20000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: MediTrust test successful",
    )
    print(response.text)
except Exception as e:
    print("Test failed:", type(e).__name__, str(e))
finally:
    client.close()