import sqlite3
import os

# Folder containing your existing DBs
DB_FOLDER = "dbs"  # change to your folder path
MASTER_DB = "master_questions.db"

# Create Master DB
master_conn = sqlite3.connect(MASTER_DB)
mcur = master_conn.cursor()

# Create schema
mcur.execute("""
CREATE TABLE IF NOT EXISTS papers (
    paper_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    instructions TEXT,
    total_questions INTEGER
);
""")

mcur.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_answer TEXT,
    correct_option CHAR(1),
    explanation TEXT,
    topic TEXT,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
);
""")

# Loop over each DB and merge
for db_file in os.listdir(DB_FOLDER):
    if db_file.endswith(".db"):
        db_path = os.path.join(DB_FOLDER, db_file)

        # Decide paper type
        paper_type = "mock" if "mock" in db_file.lower() else "practice"
        paper_title = os.path.splitext(db_file)[0]
        
        print(f"📥 Importing from {db_file} ({paper_type})")

        # Insert into papers table
        mcur.execute("INSERT INTO papers (title, type, instructions, total_questions) VALUES (?, ?, ?, ?)",
                     (paper_title, paper_type, "Answer all questions carefully.", 0))
        paper_id = mcur.lastrowid

        # Read old DB
        old_conn = sqlite3.connect(db_path)
        ocur = old_conn.cursor()
        ocur.execute("SELECT question, option_a, option_b, option_c, option_d, correct_answer, correct_option, explanation, topic FROM questions")
        rows = ocur.fetchall()

        # Insert questions
        for row in rows:
            mcur.execute("""
                INSERT INTO questions 
                (paper_id, question, option_a, option_b, option_c, option_d, correct_answer, correct_option, explanation, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (paper_id, *row))

        # Update total_questions
        mcur.execute("UPDATE papers SET total_questions = ? WHERE paper_id = ?", (len(rows), paper_id))

        old_conn.close()

# Save master DB
master_conn.commit()
master_conn.close()

print(f"✅ Merged all DBs into {MASTER_DB}")
