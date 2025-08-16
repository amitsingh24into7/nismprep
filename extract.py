import pytesseract
from pdf2image import convert_from_path
import json
import re
import os

# Set tesseract path if needed (update this path if yours is different)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\AmitKumarSingh\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# PDF file path
pdf_path = "qbank/NISM DEMO 4.pdf"

# Step 1: Convert PDF to text using OCR
images = convert_from_path(pdf_path, dpi=300)

full_text = ""
for image in images:
    full_text += pytesseract.image_to_string(image) + "\n"

# Optional: Save raw OCR text for debugging
with open("raw_ocr_output_4.txt", "w", encoding="utf-8") as f:
    f.write(full_text)
print("📄 Saved raw OCR text to 'raw_ocr_output.txt'")

# Step 2: Extract questions using regex
def extract_questions(text):
    blocks = re.split(r'\n(?=\d{1,3}\.\s)', text)  # Splits at lines like "1. ", "23. ", etc.
    qa_pairs = []

    for block in blocks:
        block = block.strip()

        # Extract question
        q_match = re.match(r'\d{1,3}\.\s*(.*)', block)
        question = q_match.group(1).strip() if q_match else ""

        # Extract options
        options = re.findall(r'\(?[a-dA-D]\)?[\).:\s]+([^\n]+)', block)
        if len(options) < 4:
            continue  # Skip if not 4 options

        # Extract correct answer (can vary)
        ans_match = re.search(r"(?i)correct answer[:\s]*[\(]?([a-dA-D])[\)]?", block)
        correct = ans_match.group(1).lower() if ans_match else ""

        # Extract explanation
        expl_match = re.search(r"(?i)explanation[:\s]*(.+)", block, re.DOTALL)
        explanation = expl_match.group(1).strip() if expl_match else ""

        # Store the QA pair
        qa_pairs.append({
            "question_block": block,
            "question": question,
            "option_a": options[0].strip(),
            "option_b": options[1].strip(),
            "option_c": options[2].strip(),
            "option_d": options[3].strip(),
            "correct_option": correct,
            "explanation": explanation
        })

    return qa_pairs

questions = extract_questions(full_text)

# Step 3: Save structured data to JSON
with open("nism_questions_4.json", "w", encoding="utf-8") as f:
    json.dump(questions, f, indent=4, ensure_ascii=False)

print(f"✅ Extracted {len(questions)} questions to 'nism_questions.json'")
