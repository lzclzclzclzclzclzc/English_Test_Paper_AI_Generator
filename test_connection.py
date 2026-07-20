"""Single-turn chat test using openai SDK.

Run:
    python test_connection.py
"""
import os
from openai import OpenAI

API_KEY  = os.getenv("LLM_API_KEY",  "sk-bd715a2930c44d219331824a5e9217e8")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
MODEL    = os.getenv("LLM_MODEL",    "deepseek-v4-flash")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

prompt = input("你: ").strip()
if not prompt:
    print("(空输入，退出)")
    exit()

print("\n助手: ", end="", flush=True)
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
)
print(response.choices[0].message.content)
