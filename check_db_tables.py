import sqlite3

conn = sqlite3.connect('flashcards.db')
cur = conn.cursor()

print('=== テーブル一覧 ===')
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
for t in tables:
    print(t[0])

print('\n=== usersテーブルのスキーマ ===')
cur.execute("PRAGMA table_info(users);")
for row in cur.fetchall():
    print(row)

conn.close() 