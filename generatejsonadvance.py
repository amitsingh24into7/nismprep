import os
import re
import json
import pytesseract
from pdf2image import convert_from_path
from groq import Groq

# ======================
# CONFIG
# ======================
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\AmitKumarSingh\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
PDF_PATH = "qbank/NISM DEMO 3.pdf"
OUTPUT_DIR = "pages_text31"
FINAL_JSON_FILE = "nism_questions_final_3.json"
MODEL_NAME = "llama3-70b-8192"
GROQ_API_KEY = "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"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ======================
# STEP 1: OCR PER PAGE
# ======================
print("📄 Converting PDF to images...")
images = convert_from_path(PDF_PATH, dpi=300)

print(f"🔹 Found {len(images)} pages")
for idx, image in enumerate(images, start=1):
    page_text = pytesseract.image_to_string(image)
    page_file = os.path.join(OUTPUT_DIR, f"page_{idx}.txt")
    with open(page_file, "w", encoding="utf-8") as f:
        f.write(page_text)
    print(f"✅ Saved OCR text: {page_file}")

# ======================
# STEP 2: Process each page with Groq
# ======================
client = Groq(api_key=GROQ_API_KEY)
all_questions = []

for page_file in sorted(os.listdir(OUTPUT_DIR)):
    if not page_file.endswith(".txt"):
        continue

    with open(os.path.join(OUTPUT_DIR, page_file), "r", encoding="utf-8") as f:
        page_text = f.read().strip()

    if not page_text:
        continue

    prompt = f"""
You are given OCR-extracted exam question text from a PDF page.

Convert it into a clean JSON array where each object is:
{{
    "question_number": "string",
    "question_text": "string",
    "options": ["string1", "string2", "string3", "string4"],
    "correct_answer": "string",
    "explanation": "string",
    "topic": "string"
}}

Rules:
- Keep original question numbers from the text if present.
- Fix obvious OCR typos.
- If there is no explanation, leave it as an empty string "".
- The "topic" should be a concise category describing the subject of the question 
  (e.g., "Options Pricing", "Futures Trading", "Regulatory Compliance", 
  "Market Participants", "Risk Management", etc.).
- If topic is unclear, infer the most appropriate one from the question and explanation.
- Do not add anything outside JSON.

Here is the page text:
---
{page_text}
"""


    print(f"🤖 Processing {page_file}...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a JSON data extractor."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=3000
    )

    json_str = response.choices[0].message.content.strip()

    try:
        page_data = json.loads(json_str)
        all_questions.extend(page_data)
        print(f"✅ Parsed {len(page_data)} questions from {page_file}")
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error in {page_file}: {e}")
        print(json_str)
        continue

# ======================
# STEP 3: Save merged JSON
# ======================
with open(FINAL_JSON_FILE, "w", encoding="utf-8") as f:
    json.dump(all_questions, f, indent=2, ensure_ascii=False)

print(f"🎯 Done! {len(all_questions)} total questions saved to {FINAL_JSON_FILE}")
