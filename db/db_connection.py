# db/connection.py
import psycopg2
import bcrypt
from contextlib import contextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database config from .env
# Supabase DB Config
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),         # e.g., "db.xxxxx.supabase.co"
    "database": os.getenv("DB_NAME"),     # usually "postgres"
    "user": os.getenv("DB_USER"),         # e.g., "postgres"
    "password": os.getenv("DB_PASS"),
    "port": 5432,
    "sslmode": "require"  # Supabase requires SSL
}

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))