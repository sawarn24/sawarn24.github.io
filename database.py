import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        print("Database connected successfully!")
        return conn
    except Exception as e:
        print("Error connecting to database:", e)
        raise e