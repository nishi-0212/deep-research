import json
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
_client = Groq() if os.getenv("GROQ_API_KEY") else None


def available() -> bool:
    return _client is not None


def ask_json(system: str, user: str, max_tokens: int = 1500):
    resp = _client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens + 3000,   # room for reasoning tokens
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return json.loads(text)