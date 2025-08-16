import sqlite3
import json
import os

# ==== CONFIG ====
DB_FILE = "nism_questions_final_final.db"  # SQLite DB file name
JSON_FILE = "nism_questions_final_final.json"  # Input JSON file

# ==== CREATE DB & TABLE ====
def create_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_answer TEXT,
            correct_option CHAR(1),
            explanation TEXT,
            topic TEXT
        )
    """)
    conn.commit()
    conn.close()


# ==== INSERT OR UPDATE ====
def insert_or_update(data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for idx, q in enumerate(data, start=1):
        question_text = q.get("question_text", "").strip()
        options = q.get("options", [])
        
        # Fill missing options with None
        option_a = options[0] if len(options) > 0 else None
        option_b = options[1] if len(options) > 1 else None
        option_c = options[2] if len(options) > 2 else None
        option_d = options[3] if len(options) > 3 else None

        correct_answer = q.get("correct_answer", "").strip()
        
        # Find correct option letter (A/B/C/D) if it matches one of the options
        correct_option = None
        for letter, opt in zip(['A', 'B', 'C', 'D'], [option_a, option_b, option_c, option_d]):
            if opt and opt.strip().lower() == correct_answer.strip().lower():
                correct_option = letter
                break

        explanation = q.get("explanation", "").strip()
        topic = q.get("topic", "").strip()

        # UPSERT: update if question exists, else insert
        cursor.execute("""
            SELECT id FROM questions WHERE question = ?
        """, (question_text,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE questions
                SET option_a=?, option_b=?, option_c=?, option_d=?,
                    correct_answer=?, correct_option=?, explanation=?, topic=?
                WHERE id=?
            """, (option_a, option_b, option_c, option_d,
                  correct_answer, correct_option, explanation, topic, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO questions
                (question, option_a, option_b, option_c, option_d,
                 correct_answer, correct_option, explanation, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (question_text, option_a, option_b, option_c, option_d,
                  correct_answer, correct_option, explanation, topic))

    conn.commit()
    conn.close()


# ==== MAIN ====
if __name__ == "__main__":
    if not os.path.exists(JSON_FILE):
        print(f"JSON file not found: {JSON_FILE}")
        exit()

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    create_db()
    insert_or_update(questions_data)

    print(f"✅ Database '{DB_FILE}' updated successfully with {len(questions_data)} questions.")
