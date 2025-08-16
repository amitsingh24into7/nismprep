import re
import json

def parse_ocr_questions(file_path):
    """
    Parses the OCR text file and extracts structured question data.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f] # Read lines, preserving internal spaces

    questions = []
    current_question = None
    explanation_buffer = []
    collecting_explanation = False

    # --- Helper Functions ---
    def is_question_start(line):
        # Matches lines like 'Q7.', '9. Fs -', '240.', 'O13)', 'Q 25.', '12.', 'Q20.', 'Qa47.' etc.
        # It's tricky because of OCR artifacts. Look for a number followed by a separator near the start.
        # Also catches standalone numbers that seem to be question starters (like '9. Fs -')
        start_part = line[:15] # Check only the beginning of the line
        # Pattern: optional 'Q' or 'O', optional space, digits, optional separator (., ), :)
        return bool(re.match(r'^\s*[QO]?\s*\d+[\.\):\s]*', start_part)) or \
               bool(re.match(r'^\s*\d+\.\s*[A-Za-z]', line)) # e.g., '9. Fs -'

    def is_option(line):
        # Matches lines starting with an option letter (A-D/a-d), followed by separator or space
        return bool(re.match(r'^\s*[A-Da-d][\.\)]?\s+', line))

    def extract_question_number(line):
        # Extracts the question number from the start of a line
        match = re.search(r'[QO]?\s*(\d+)[\.\):\s]*', line)
        if match:
            return match.group(1)
        # Handle cases like '9. Fs -'
        match = re.search(r'^\s*(\d+)\.', line)
        if match:
            return match.group(1)
        return "Not specified"

    def extract_correct_answer_marker(line):
        # Checks if a line indicates the correct answer and extracts the answer text if possible
        # Handles various markers and formats
        markers = [r'v\s*¥?\s*CORRECT\s*ANS?WER', r'¥+\s*CORRECT\s*ANS?WER', r'Y+\s*CORRECT\s*ANS?WER', r'CORRECT\s*ANS?WER\s*[:\-]?', r'>\s*WRONG\s*ANSWER']
        for marker_pattern in markers[:-1]: # Check correct answer markers first
             if re.search(marker_pattern, line, re.IGNORECASE):
                # Try to extract answer text after the marker
                # e.g., "v CORRECT ANSWER 4a" or "¥ CORRECT ANSWER" (answer on next line is handled elsewhere)
                # Or "CORRECT ANSWER: False"
                answer_part = re.split(marker_pattern, line, flags=re.IGNORECASE, maxsplit=1)[-1].strip()
                if answer_part and not re.match(r'^[4a]$', answer_part): # '4a' seems to be an OCR artifact
                    # Check if it's just a letter (A/B/C/D)
                    if re.fullmatch(r'[A-Da-d]', answer_part):
                        return answer_part.upper()
                    # Otherwise, it might be the full text (like "False", "Higher the volatility, higher the initial margin")
                    # We'll use this if we can't map it to an option letter later.
                    # For now, just return the part found.
                    return answer_part
                return True # Marker found, but no answer text on same line
        # Check for WRONG ANSWER marker (to ignore it)
        if re.search(markers[-1], line, re.IGNORECASE):
             return "WRONG_ANSWER_MARKER"
        return None # No marker found

    def finalize_question(q):
        # Final processing before adding to list
        if q:
            # Clean up text
            q["question_text"] = re.sub(r'\s+', ' ', q["question_text"]).strip()
            q["explanation"] = re.sub(r'\s+', ' ', q["explanation"]).strip()

            # Assign topic
            q["topic"] = infer_topic(q)
        return q

    def infer_topic(q):
        # Simple keyword-based topic inference
        text = f"{q['question_text']} {' '.join(q['options'])} {q['explanation']}".lower()
        
        # Define topic keywords
        topics = {
            "Options Basics": ["call option", "put option", "strike price", "exercise price", "right but not obligation", "european", "american"],
            "Options Greeks": ["delta", "gamma", "theta", "vega", "rho", "sensitivity", "volatility"],
            "Options Pricing": ["premium", "intrinsic value", "time value", "in-the-money", "out-of-the-money", "at-the-money"],
            "Futures Trading": ["futures contract", "long position", "short position", "lot size", "squaring off"],
            "Derivatives Margining": ["initial margin", "value at risk", "var", "mark to market", "mtm"],
            "Clearing & Settlement": ["clearing member", "non-clearing member", "clearing corporation", "settlement", "liquid assets"],
            "Risk Management": ["risk", "hedge", "hedgers", "speculators", "stop loss", "position limits"],
            "Market Microstructure & Liquidity": ["impact cost", "liquidity"],
            "Portfolio Risk": ["diversification", "systematic risk", "unsystematic risk"],
            "Regulatory Compliance": ["complaints", "unauthorized transaction", "scores", "sebi"],
            "Index Construction": ["nifty", "index", "stock split", "market capitalization", "weightage"],
            "Forward vs Futures": ["forward contract", "bilateral contract"],
            "Derivatives Accounting": ["accounting", "profit and loss", "amortized", "income"],
            "Futures Arbitrage": ["calendar spread"],
            "Investment Principles": ["risk-free", "returns", "investment"]
        }
        
        scores = {}
        for topic, keywords in topics.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[topic] = score
        
        if scores:
            # Return the topic with the highest score
            return max(scores, key=scores.get)
        return "General"

    # --- Main Parsing Loop ---
    i = 0
    while i < len(lines):
        line = lines[i]

        # --- 1. Identify Start of New Question ---
        if is_question_start(line):
            # Finalize previous question if exists
            if current_question:
                # If we were collecting an explanation for the previous question and hit a new Q, finalize it.
                if collecting_explanation:
                    current_question["explanation"] = " ".join(explanation_buffer).strip()
                    explanation_buffer = []
                    collecting_explanation = False
                q = finalize_question(current_question)
                if q and q["question_text"]: # Only append if it has content
                    questions.append(q)

            # Start new question
            q_num = extract_question_number(line)
            # Extract the rest of the line as the beginning of the question text
            # Handle cases like '9. Fs -' where 'Fs -' is part of the question
            q_text_start_match = re.search(r'(?:[QO]?\s*\d+[\.\):\s]*)+(.*)', line)
            if q_text_start_match:
                q_text_start = q_text_start_match.group(1).strip()
            else:
                # Fallback for cases like '9. Fs -'
                q_text_start = re.sub(r'^\s*\d+\.\s*', '', line, count=1).strip()

            current_question = {
                "question_number": q_num,
                "question_text": q_text_start,
                "options": [],
                "correct_answer": None, # Will store the text of the correct answer
                "correct_answer_letter": None, # Will store the letter (A/B/C/D) if found directly
                "explanation": ""
            }
            i += 1
            continue # Move to next line

        # --- 2. Process Lines Within a Question ---
        if current_question:
            # --- 2a. Collect Options ---
            if is_option(line):
                # Clean the option text (remove 'A) ' part)
                option_text = re.sub(r'^\s*[A-Da-d][\.\)]?\s*', '', line).strip()
                current_question["options"].append(option_text)
                i += 1
                continue

            # --- 2b. Look for Correct Answer Marker ---
            marker_result = extract_correct_answer_marker(line)
            if marker_result:
                if marker_result == "WRONG_ANSWER_MARKER":
                    # Ignore this line
                    pass
                elif marker_result == True:
                    # Marker found, answer might be on this or next line
                    # Check next line for a standalone letter or text
                    if i + 1 < len(lines):
                        next_line = lines[i+1].strip()
                        if re.fullmatch(r'[A-Da-d]', next_line):
                            current_question["correct_answer_letter"] = next_line.upper()
                        elif next_line and not is_question_start(next_line) and not is_option(next_line):
                            # Assume next line is the answer text if it's not a new Q or option
                            current_question["correct_answer"] = next_line
                        # If next line is a new Q or option, we might have to backtrack or use option matching
                elif isinstance(marker_result, str): # Answer text found on same line
                     if re.fullmatch(r'[A-Da-d]', marker_result):
                        current_question["correct_answer_letter"] = marker_result.upper()
                     else:
                         current_question["correct_answer"] = marker_result
                i += 1
                continue

            # --- 2c. Start of Explanation ---
            if line.lower().startswith('explanation'):
                collecting_explanation = True
                # Extract text after 'Explanation:' if any
                expl_text = line[11:].strip() # Remove 'Explanation' (case handled by .lower())
                if expl_text:
                    explanation_buffer.append(expl_text)
                i += 1
                continue

            # --- 2d. Collect Explanation Lines ---
            if collecting_explanation:
                # Stop collecting if we hit a new question start or an option (rare, but possible mid-explanation artifact)
                if is_question_start(line) or is_option(line):
                     current_question["explanation"] = " ".join(explanation_buffer).strip()
                     explanation_buffer = []
                     collecting_explanation = False
                     # Do not increment i, let the outer loop handle this line as a potential new question/option
                     continue
                else:
                    explanation_buffer.append(line)
                    i += 1
                    continue

            # --- 2e. Add to Question Text (if not explanation, option, or marker) ---
            # This handles cases where the question text spans multiple lines before options appear
            if not collecting_explanation and not is_option(line) and not extract_correct_answer_marker(line):
                # Avoid adding lines that are just OCR artifacts like '4a' or standalone letters
                # if they appear outside of options/answers.
                if not re.fullmatch(r'\d+[a-zA-Z]?', line.strip()) and not re.fullmatch(r'[A-Da-d]', line.strip()):
                    current_question["question_text"] += " " + line
            # else: line is likely an artifact or part of a section we are already handling

        i += 1 # Move to next line

    # --- 3. Finalize Last Question ---
    if current_question:
        if collecting_explanation:
            current_question["explanation"] = " ".join(explanation_buffer).strip()
        q = finalize_question(current_question)
        if q and q["question_text"]:
            questions.append(q)

    # --- 4. Post-process: Map Correct Answer Letter to Text ---
    for q in questions:
        if q["correct_answer_letter"] and not q["correct_answer"]:
            # Map letter to option text
            letter_index = ord(q["correct_answer_letter"]) - ord('A')
            if 0 <= letter_index < len(q["options"]):
                q["correct_answer"] = q["options"][letter_index]
        # Fallback if still no correct answer
        if not q["correct_answer"] and q["options"]:
            q["correct_answer"] = q["options"][0] # Or decide on a better default/error strategy
        # Clean up temporary field
        if "correct_answer_letter" in q:
            del q["correct_answer_letter"]

    return questions

def save_json(data, output_path):
    """Saves the data to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Successfully saved {len(data)} questions to '{output_path}'")

# --- Main Execution ---
if __name__ == "__main__":
    input_file = "raw_ocr_output.txt"
    output_file = "questions_bank.json"

    print(f"Starting to parse '{input_file}'...")
    try:
        parsed_questions = parse_ocr_questions(input_file)
        print(f"Parsing complete. Found {len(parsed_questions)} questions.")
        save_json(parsed_questions, output_file)
        print("Process finished.")
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found. Please check the filename and path.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
