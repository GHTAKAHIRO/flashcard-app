import sqlite3
import os
from werkzeug.security import generate_password_hash

def recreate_database():
    # 既存のデータベースファイルを削除
    if os.path.exists('flashcards.db'):
        os.remove('flashcards.db')
    
    # 新しいデータベースを作成
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    try:
        # usersテーブルの作成
        cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
        ''')
        
        # 管理者ユーザーの作成
        password_hash = generate_password_hash('admin123')
        cursor.execute('''
        INSERT INTO users (username, password_hash, full_name, is_admin)
        VALUES (?, ?, ?, ?)
        ''', ('admin', password_hash, '管理者', 1))
        
        # その他の必要なテーブルを作成
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT,
            source TEXT,
            page_range TEXT,
            difficulty TEXT,
            PRIMARY KEY (user_id, source)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            source TEXT,
            card_id TEXT,
            result TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        print("データベースの再作成が完了しました")
        print("管理者ユーザーの情報:")
        print("ユーザー名: admin")
        print("パスワード: admin123")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    recreate_database() 