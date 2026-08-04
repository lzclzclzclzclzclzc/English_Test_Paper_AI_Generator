"""Single-turn chat test using openai SDK.

Run:
    python test_connection.py
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY  = os.environ["LLM_API_KEY"]
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
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
