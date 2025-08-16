import os
import re
import json
from groq import Groq

# ==== CONFIG ====
GROQ_API_KEY = "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"
INPUT_FILE = "raw_ocr_output_31.txt"
OUTPUT_FILE = "nism_questions_32.json"
MODEL_NAME = "llama3-70b-8192"
QUESTIONS_PER_CHUNK = 10

# ==== READ INPUT FILE ====
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    raw_text = f.read()

# ==== EXTRACT QUESTIONS ====
# Capture: Q<number> (optional dot), then all text until next Q<number> or EOF
pattern = r"(?:Q|Question\s*)?(\d+)\s*(.*?)\s*(?=(?:Q|Question\s*)\d+|$)"
matches = re.findall(pattern, raw_text, flags=re.S | re.I)

# Build clean blocks
question_blocks = []
for num, text in matches:
    block = f"Q{num}\n{text.strip()}"
    question_blocks.append(block)

# ==== CHUNK QUESTIONS ====
chunks = [question_blocks[i:i+QUESTIONS_PER_CHUNK] for i in range(0, len(question_blocks), QUESTIONS_PER_CHUNK)]

client = Groq(api_key=GROQ_API_KEY)
all_questions = []

for idx, chunk in enumerate(chunks, start=1):
    chunk_text = "\n\n".join(chunk)
    prompt = f"""
You are given unstructured exam question text extracted via OCR.

Convert it into a clean JSON array where each object is:
{{
    "question_number": "string",
    "question_text": "string",
    "options": ["string1", "string2", "string3", "string4"],
    "correct_answer": "string",
    "explanation": "string"
}}

Rules:
- Do NOT add text outside JSON.
- Use the question number from the text (do not renumber).
- Preserve all numbers and text exactly, only fix OCR typos.

Here is the chunk:
---
{chunk_text}
"""

    print(f"🔹 Processing chunk {idx}/{len(chunks)}...")
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
        parsed = json.loads(json_str)
        all_questions.extend(parsed)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error in chunk {idx}: {e}")
        print("Raw output:\n", json_str)
        continue

# ==== SAVE ====
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_questions, f, indent=2, ensure_ascii=False)

print(f"✅ Done. {len(all_questions)} questions saved to {OUTPUT_FILE}")
