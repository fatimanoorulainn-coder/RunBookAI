from dotenv import load_dotenv
import os

from groq import Groq


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY not found")


client = Groq(
    api_key=api_key
)


response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {
            "role": "user",
            "content": "Explain Kubernetes pods in one sentence."
        }
    ]
)


print(response.choices[0].message.content)