"""End-to-end test for writing grade endpoint."""
import requests
import json

BASE = "http://127.0.0.1:8000/api"
session = requests.Session()

# Step 1: Login (cookie-based)
print("=== Step 1: Login ===")
r = session.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"})
print(f"Login: {r.status_code}, user: {r.json().get('username')}")

# Step 2: Generate a paper with writing question
print("\n=== Step 2: Generate paper with writing ===")
r = session.post(
    f"{BASE}/papers/generate",
    json={
        "user_query": "出1道英语作文题",
        "mode": "fresh",
    },
)
print(f"Generate paper status: {r.status_code}")
print(f"Response keys: {list(r.json().keys())}")
paper_data = r.json()
paper_id = paper_data.get("paper_id") or paper_data.get("id")
if not paper_id:
    print(f"Full response: {json.dumps(paper_data, ensure_ascii=False)[:500]}")
    exit(1)

print(f"Paper generated: {paper_id}")
items = paper_data.get("items", [])
print(f"Items: {len(items)}")
for item in items:
    q = item.get("question", {})
    print(f"  - Index {item.get('index')}: type={q.get('question_type')}, stem={q.get('stem', '')[:40]}")

# Step 3: Grade writing
print("\n=== Step 3: Grade writing ===")
writing_item = None
for item in items:
    q = item.get("question", {})
    if q.get("question_type") == "writing":
        writing_item = item
        break

if writing_item:
    essay = """Dear teacher,

I want to say thank you for helping me with my English. When I had difficulty in learning English grammar, you always encouraged me to practice more. It was very kind of you to stay after school and help me with my homework.

I felt so grateful and happy at that time. Now I want to tell you that I will keep working hard on my English. I will never forget your help.

Thank you again!

Yours sincerely,
Li Ming"""

    r = session.post(
        f"{BASE}/writing/grade",
        json={
            "paper_id": paper_id,
            "items": [{"index": writing_item["index"], "user_essay": essay}],
        },
    )
    print(f"Grade response: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        for item in result["results"]:
            print(f"  Index: {item['index']}")
            print(f"  Total Score: {item['total_score']} / 20")
            print(f"  Content: {item['content_score']} / 8")
            print(f"  Language: {item['language_score']} / 8")
            print(f"  Organization: {item['organization_score']} / 4")
            print(f"  Word Count: {item['word_count']}")
            print(f"  Level: {item['level']}")
            print(f"  Content Analysis (member-only): {item['content_analysis']}")
            print(f"  Language Analysis (member-only): {item['language_analysis']}")
            print(f"  Has revised version: {bool(item['revised_version'])}")
    else:
        print(f"Error: {r.text[:500]}")
else:
    print("No writing item found in paper!")

print("\n=== Test Complete ===")