import os
import json
import shutil
import pytesseract
from pdf2image import convert_from_path
from groq import Groq
import argparse
from dotenv import load_dotenv
load_dotenv()

# ====== CONFIG ======
PDF_PATH = "qbank/NISM SECOND 100 FINAL TEST.pdf"
OUTPUT_DIR = "pagesfinal"
FAILED_DIR = "failed_pagesfinal"
FINAL_JSON_FILE = "nism_questions_final_final.json"
MODEL_NAME = "llama3-70b-8192"  # Groq model

# Set tesseract path if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\AmitKumarSingh\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Groq API key
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ====== LLM JSON parser ======
def parse_page_with_llm(page_text, strict=False):
    """Send OCR text to LLM and return parsed JSON or None"""
    if not strict:
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
- If there is no explanation, leave it as "".
- "topic" should be a concise category describing the question.
- Do not output anything outside JSON.

Here is the page text:
---
{page_text}
"""
    else:
        prompt = f"""
STRICT MODE:
Convert the following text into a VALID JSON array only. 
No comments, no markdown, no explanations — just JSON.

Format:
[
  {{
    "question_number": "string",
    "question_text": "string",
    "options": ["string1", "string2", "string3", "string4"],
    "correct_answer": "string",
    "explanation": "string",
    "topic": "string"
  }}
]

Make sure:
- Escape quotes inside strings.
- Do not add trailing commas.
- Options must be exactly 4.
- Output must start with [ and end with ].

TEXT:
---
{page_text}
"""

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
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

# ====== PDF → OCR ======
def extract_pages_from_pdf():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("📄 Converting PDF to images...")
    images = convert_from_path(PDF_PATH, dpi=300)

    for i, image in enumerate(images, start=1):
        page_img = os.path.join(OUTPUT_DIR, f"page_{i}.png")
        page_txt = os.path.join(OUTPUT_DIR, f"page_{i}.txt")
        image.save(page_img, "PNG")

        text = pytesseract.image_to_string(image)
        with open(page_txt, "w", encoding="utf-8") as f:
            f.write(text.strip())

        print(f"✅ Saved OCR: {page_txt}")

# ====== Process pages ======
def process_pages(retry_only=False):
    os.makedirs(FAILED_DIR, exist_ok=True)

    all_questions = []
    failed_pages = []

    page_list = sorted(os.listdir(FAILED_DIR if retry_only else OUTPUT_DIR))
    page_list = [p for p in page_list if p.endswith(".txt")]

    for page_file in page_list:
        with open(os.path.join(FAILED_DIR if retry_only else OUTPUT_DIR, page_file), "r", encoding="utf-8") as f:
            page_text = f.read().strip()

        if not page_text:
            print(f"⚠️ Empty: {page_file}")
            continue

        print(f"🤖 Processing {page_file}...")
        page_data = parse_page_with_llm(page_text, strict=False)

        if page_data is None:
            print(f"⚠️ Retry in strict mode: {page_file}")
            page_data = parse_page_with_llm(page_text, strict=True)

        if page_data is None:
            print(f"❌ Failed: {page_file}")
            failed_pages.append(page_file)
            shutil.copy(
                os.path.join(OUTPUT_DIR if not retry_only else FAILED_DIR, page_file),
                os.path.join(FAILED_DIR, page_file)
            )
            img_file = page_file.replace(".txt", ".png")
            if os.path.exists(os.path.join(OUTPUT_DIR, img_file)):
                shutil.copy(os.path.join(OUTPUT_DIR, img_file), os.path.join(FAILED_DIR, img_file))
        else:
            all_questions.extend(page_data)

    # Merge with old data if retry_only
    if retry_only and os.path.exists(FINAL_JSON_FILE):
        with open(FINAL_JSON_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        all_questions.extend(old_data)

    with open(FINAL_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, indent=2, ensure_ascii=False)

    print(f"🎯 Done! {len(all_questions)} questions saved to {FINAL_JSON_FILE}")
    if failed_pages:
        print("\n🚨 Failed pages saved to 'failed_pages/' for manual fix:")
        print("\n".join(failed_pages))

# ====== CLI ======
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry", action="store_true", help="Retry only failed pages")
    args = parser.parse_args()

    if not args.retry:
        extract_pages_from_pdf()

    process_pages(retry_only=args.retry)
