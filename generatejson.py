"""
Robust question extraction + LLM classification script.

Usage:
  - Put your OCR text file at raw_ocr_output.txt (same folder).
  - Set GROQ_API_KEY in .env (or export in your environment).
  - pip install python-dotenv langchain-groq rapidfuzz   (rapidfuzz optional, speeds fuzzy compare)
  - python llm_extract_full.py
"""

import os
import re
import json
import math
from pathlib import Path
from dotenv import load_dotenv

# Optional: use rapidfuzz for better fuzzy matching if installed
try:
    from rapidfuzz import fuzz
    def fuzzy_ratio(a, b):
        return fuzz.token_set_ratio(a or "", b or "") / 100.0
except Exception:
    import difflib
    def fuzzy_ratio(a, b):
        a = (a or "").strip().lower()
        b = (b or "").strip().lower()
        return difflib.SequenceMatcher(None, a, b).ratio()

# Try to import Groq Chat (langchain_groq). If not available, we will fallback to heuristics only.
USE_GROQ = False
try:
    from langchain_groq import ChatGroq
    USE_GROQ = True
except Exception as e:
    print("langchain_groq not available, will fallback to non-LLM inference. Install langchain_groq to enable Groq LLM.", e)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "llama3-8b-8192")

groq_chat = None
if USE_GROQ and GROQ_API_KEY:
    groq_chat = ChatGroq(groq_api_key=GROQ_API_KEY, model_name=MODEL_NAME, temperature=0)
    print("Groq Chat initialized with model:", MODEL_NAME)
else:
    print("Groq not initialized (GROQ_API_KEY missing or langchain_groq not installed). Using fallback heuristics only.")

RAW_FILE = "raw_ocr_output.txt"
OUT_FILE = "nism_questions_final.json"
OUT_FALLBACK = "nism_questions_fallback.json"

# Helpers
def clean_line(s: str) -> str:
    if not s:
        return ""
    # Remove common OCR stray symbols and normalize spaces
    s = s.replace('\u00A5', '')  # yen symbol
    s = s.replace('¥', '')
    s = s.replace('%', '')
    s = s.replace('v', 'v ') if s.strip().startswith('v') and len(s.strip())>1 else s
    # fix weird quotes
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def is_question_start(line: str) -> bool:
    if not line:
        return False
    # Examples: "7.", "240.", "Q7.", "Q 7.", "214 a trader..."
    return bool(re.match(r'^\s*(?:Q\s*\d+|\d{1,4})[\).\s:-]', line, re.IGNORECASE))

def is_option_label(line: str) -> bool:
    if not line:
        return False
    # e.g. "a) text" "(a) text" "A)" "a." "a )"
    return bool(re.match(r'^\s*\(?\s*[A-Da-d]\s*\)?[\).:\s-]+', line))

def extract_label_and_text(line: str):
    m = re.match(r'^\s*\(?\s*([A-Da-d])\s*\)?[\).:\s-]+(.+)', line)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return None, line.strip()

def find_explanation_from_block(block_lines):
    # Find the line which starts with Explanation (case-insensitive)
    joined = "\n".join(block_lines)
    m = re.search(r'(?i)explanation[:\s]*', joined)
    if not m:
        return ""
    start = m.end()
    expl = joined[start:].strip()
    # stop at next question marker if any
    expl = re.split(r'\n\s*(?:\d+\s*[\).]|Q\d+)', expl, maxsplit=1)[0].strip()
    return expl

def partition_into_question_chunks(lines):
    """
    Line-by-line scanner that creates individual question chunks.
    Handles large blocks that contain multiple questions.
    """
    chunks = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if is_question_start(ln):
            # start a new chunk
            start_idx = i
            i += 1
            # collect until next question start OR until we've collected a potential question block (20 lines limit)
            while i < n and not is_question_start(lines[i]) and (i - start_idx) < 120:
                i += 1
            chunk = lines[start_idx:i]
            chunks.append(chunk)
        else:
            # skip stray lines until a question start
            i += 1
    return chunks

def extract_q_options_expl(chunk_lines):
    """
    From a chunk (list of lines), try to get:
      - question text (string)
      - options list of length 4 (strings) in order [a,b,c,d]
      - explanation (string)
    Returns (question, options_dict, explanation, raw_text)
    """
    # Clean lines
    clines = [clean_line(x) for x in chunk_lines if clean_line(x) != ""]
    if not clines:
        return None

    # combine contiguous initial lines as question until we detect the first option
    question_lines = []
    opts = {}
    explanation = ""
    j = 0
    # find first option label index
    first_opt_idx = None
    for idx, l in enumerate(clines):
        if is_option_label(l):
            first_opt_idx = idx
            break
    if first_opt_idx is None:
        # Try to find four candidate option lines after question using short-line heuristic
        # We'll assume the first short lines after first long question line are options
        # Find first line that's likely the question (longer than 6 words)
        for idx, l in enumerate(clines):
            if len(l.split()) >= 4:
                # consider question spans up to this index; candidate options after it
                first_opt_idx = idx + 1
                break

    if first_opt_idx is None:
        # can't reliably extract
        # treat entire chunk as question text and attempt to get explanation
        question_text = " ".join(clines[:1])
        explanation = find_explanation_from_block(clines)
        return question_text, {}, explanation, "\n".join(clines)

    # question is lines before first_opt_idx
    question_text = " ".join(clines[:first_opt_idx]).strip()

    # collect options starting at first_opt_idx:
    k = first_opt_idx
    # If options are lettered, parse them
    if is_option_label(clines[k]):
        # Parse consecutive labeled options, allow multi-line option continuation
        current_label = None
        current_text = []
        while k < len(clines):
            line = clines[k]
            if is_option_label(line):
                # finish previous
                if current_label:
                    opts[current_label] = " ".join(current_text).strip()
                lbl, txt = extract_label_and_text(line)
                current_label = lbl
                current_text = [txt]
            elif re.search(r'(?i)CORRECT\s*ANSWER|WRONG\s*ANSWER|EXPLANATION', line):
                # stop options
                break
            else:
                # continuation of current option
                if current_label:
                    current_text.append(line)
                else:
                    # stray line before first option label - ignore
                    pass
            k += 1
        # finish last option
        if current_label and current_label not in opts:
            opts[current_label] = " ".join(current_text).strip()
    else:
        # If options are not lettered, take next 4 non-empty lines as options
        cand = []
        kk = k
        while kk < len(clines) and len(cand) < 4:
            if not re.search(r'(?i)CORRECT\s*ANSWER|WRONG\s*ANSWER|EXPLANATION', clines[kk]):
                cand.append(clines[kk])
            kk += 1
        for idx, text in enumerate(cand[:4]):
            lbl = chr(ord('a') + idx)
            opts[lbl] = text.strip()

    # Normalize options order into a,b,c,d (if any missing, empty string)
    ordered = {c: opts.get(c, "") for c in ['a', 'b', 'c', 'd']}

    # explanation
    explanation = find_explanation_from_block(clines)

    return question_text.strip(), ordered, explanation.strip(), "\n".join(clines)

# LLM prompt builder - strict JSON schema + example
PROMPT_TEMPLATE = """You are an expert extractor for multiple-choice exam questions.

Input will be a compact, cleaned question block with exactly one question, 4 options and optionally an explanation/marked answer.

Format of the Input (do not change):
Question: <question text>
A) <option A text>
B) <option B text>
C) <option C text>
D) <option D text>
Explanation:
<explanation text - may be empty>

Task:
Return ONLY valid JSON (no extra text) exactly in this shape:
{{
  "question": "<the question text - trimmed>",
  "options": {{
     "a": "<text of option a>",
     "b": "<text of option b>",
     "c": "<text of option c>",
     "d": "<text of option d>"
  }},
  "correct_option": "<one of: a, b, c, d, or empty string if unknown>",
  "explanation": "<explanation text - trimmed>"
}}

Notes:
- If the explanation explicitly states which option is correct (a letter or exact option text), use that.
- If only the explanation contains the correct answer text (not the letter), deduce which of the four options exactly matches or best matches and output that letter.
- If you cannot confidently decide, return correct_option as an empty string.

Example Input:
Question: Which color is the sky on a clear day?
A) Green
B) Blue
C) Red
D) Yellow
Explanation:
Because the atmosphere scatters blue light more than other colors.

Example Output:
{{ "question": "Which color is the sky on a clear day?", "options": {{ "a": "Green", "b": "Blue", "c": "Red", "d": "Yellow" }}, "correct_option": "b", "explanation": "Because the atmosphere scatters blue light more than other colors." }}

Now process this block:
{compact_block}
"""

def extract_json_from_text(resp_text: str):
    """
    Try to extract JSON object from a model response that may contain noise.
    We find the first '{' and then find the matching closing brace using a stack, return substring.
    """
    if not resp_text or resp_text.strip() == "":
        return None
    s = resp_text.strip()
    # fast path: if s already starts with { try load
    try:
        return json.loads(s)
    except Exception:
        pass
    # find first {
    start = s.find('{')
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(s)):
        ch = s[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    candidate = s[start:end+1]
    try:
        return json.loads(candidate)
    except Exception:
        # try to be lenient: replace single quotes with double quotes (risky)
        alt = candidate.replace("'", '"')
        try:
            return json.loads(alt)
        except Exception:
            return None

def ask_llm_for_block(qtext, options_map, explanation):
    compact = f"Question: {qtext}\nA) {options_map.get('a','')}\nB) {options_map.get('b','')}\nC) {options_map.get('c','')}\nD) {options_map.get('d','')}\nExplanation:\n{explanation or ''}"
    prompt = PROMPT_TEMPLATE.format(compact_block=compact)
    if groq_chat:
        try:
            resp = groq_chat.invoke(prompt)
            out = getattr(resp, "content", str(resp))
            parsed = extract_json_from_text(out)
            return parsed, out
        except Exception as e:
            return None, f"LLM error: {e}"
    else:
        # No LLM — return None to trigger fallback
        return None, "No LLM available"

def infer_from_explanation(options_map, explanation, marked_answer_text=None):
    """Fallback inference using fuzzy matching between explanation/marked_answer and options_map."""
    # If marked_answer_text (text after CORRECT ANSWER) is present, try exact or fuzzy match
    candidate_texts = []
    if marked_answer_text:
        candidate_texts.append(marked_answer_text)
    if explanation:
        candidate_texts.append(explanation)
    best_letter = ""
    best_score = 0.0
    for cand in candidate_texts:
        for letter, opt_text in options_map.items():
            if not opt_text:
                continue
            score = fuzzy_ratio(opt_text, cand)
            # prefer exact normalization match
            if score > best_score:
                best_score = score
                best_letter = letter
    return (best_letter, best_score)

def find_marked_answer_in_raw(raw_block):
    # Try to pick up the explicit "CORRECT ANSWER" text lines
    m = re.search(r'(?i)CORRECT\s*ANSWER[:\s-]*([^\n\r]*)', raw_block)
    if m:
        cand = m.group(1).strip()
        if cand:
            return cand
    # try next-line after token
    lines = raw_block.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r'(?i)CORRECT\s*ANSWER', ln):
            if i+1 < len(lines):
                nxt = lines[i+1].strip()
                if nxt:
                    return nxt
    return ""

def run():
    txt = Path(RAW_FILE).read_text(encoding="utf-8")
    # pre-clean common artifacts
    txt = txt.replace('\r\n', '\n')
    txt = re.sub(r'[\u00A5¥%►•\uf0b7]', ' ', txt)
    lines = [ln.rstrip() for ln in txt.splitlines()]

    # Partition into chunks (each chunk should ideally contain exactly one question)
    chunks = partition_into_question_chunks(lines)
    print(f"Detected {len(chunks)} raw chunks (may contain one question each).")

    results = []
    fallback = []
    for idx, chunk in enumerate(chunks, start=1):
        q_extract = extract_q_options_expl(chunk)
        if not q_extract:
            continue
        qtext, options_map, explanation, raw_text = q_extract
        # If we couldn't find 4 options, try to skip; but still attempt
        missing_opts = sum(1 for v in options_map.values() if not v)
        # find explicit marked answer text in raw chunk (if present)
        marked = find_marked_answer_in_raw(raw_text)

        # Build LLM prompt only if groq_chat present
        parsed_json, raw_llm_out = None, ""
        if groq_chat:
            parsed_json, raw_llm_out = ask_llm_for_block(qtext, options_map, explanation)
        # If LLM returned valid JSON and question present, accept it
        accepted = False
        if isinstance(parsed_json, dict) and parsed_json.get("question"):
            # quick validation: ensure options exist
            opts = parsed_json.get("options", {})
            if isinstance(opts, dict) and (opts.get("a") or opts.get("b") or opts.get("c") or opts.get("d")):
                # fill any missing fields from our extraction
                parsed_json["options"] = {
                    "a": opts.get("a") or options_map.get("a",""),
                    "b": opts.get("b") or options_map.get("b",""),
                    "c": opts.get("c") or options_map.get("c",""),
                    "d": opts.get("d") or options_map.get("d",""),
                }
                if "explanation" not in parsed_json or not parsed_json["explanation"]:
                    parsed_json["explanation"] = explanation
                accepted = True

        if accepted:
            results.append(parsed_json)
            continue

        # LLM not available OR invalid JSON -> fallback inference
        # Try to infer correct option letter by:
        # 1) If marked line contains a letter (a/b/c/d or A/B/C/D), pick it
        corrected_letter = ""
        if marked:
            # if marked is a single letter or ends with a letter
            m = re.search(r'([A-Da-d])\b', marked)
            if m:
                corrected_letter = m.group(1).lower()
        # 2) If mark is a full text, fuzzy match to options
        if not corrected_letter and marked:
            best_letter, score = infer_from_explanation(options_map, "", marked)
            if best_letter and score > 0.7:
                corrected_letter = best_letter

        # 3) try using explanation text fuzzy match
        if not corrected_letter and explanation:
            best_letter, score = infer_from_explanation(options_map, explanation, None)
            if best_letter and score > 0.7:
                corrected_letter = best_letter

        # Build record (from fallback)
        rec = {
            "question": qtext,
            "options": options_map,
            "correct_option": corrected_letter,
            "explanation": explanation,
            "raw_chunk": raw_text,
            "llm_raw": raw_llm_out,
            "confidence_est": round(float(1.0 if corrected_letter else 0.0), 3)
        }
        # If we have some candidate but low score, flag as fallback
        if corrected_letter:
            results.append(rec)
        else:
            fallback.append(rec)

    # Save outputs
    Path(OUT_FILE).write_text(json.dumps(results, indent=4, ensure_ascii=False), encoding="utf-8")
    Path(OUT_FALLBACK).write_text(json.dumps(fallback, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Parsed {len(results)} questions (saved to {OUT_FILE}).")
    print(f"Fallback / uncertain items: {len(fallback)} (saved to {OUT_FALLBACK}).")
    # Print first few parsed entries for quick sanity check
    if results:
        print("\nFirst parsed sample:")
        print(json.dumps(results[0], indent=2, ensure_ascii=False))
    if fallback:
        print("\nFirst fallback sample (needs manual review):")
        print(json.dumps(fallback[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
