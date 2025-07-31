import sqlite3
import os

print("Checking database...")
db_path = 'flashcards.db'

if os.path.exists(db_path):
    print(f"Database exists: {db_path}")
    print(f"Size: {os.path.getsize(db_path)} bytes")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"User count: {count}")
        
        cursor.execute("SELECT username, created_at FROM users ORDER BY id DESC LIMIT 3")
        users = cursor.fetchall()
        for user in users:
            print(f"User: {user[0]}, Created: {user[1]}")
        
        conn.close()
        print("Database check completed successfully")
        
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Database file not found") 