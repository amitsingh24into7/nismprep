import sqlite3
import json
import os

# ==== CONFIG ====
DB_FILE = "master_questions.db"  # SQLite DB file name


# ==== CREATE DB & TABLE ====
def create_db():
    # Create Master DB
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS papers (
        paper_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        instructions TEXT,
        total_questions INTEGER
    );
    """)

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE user_progress (
            user_id INTEGER NOT NULL,
            paper_id INTEGER NOT NULL,
            answered_count INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0, -- 0 = not finished, 1 = completed
            PRIMARY KEY (user_id, paper_id)
        )
    """)
    conn.commit()
    conn.close()


# ==== MAIN ====
if __name__ == "__main__":
    create_db()
