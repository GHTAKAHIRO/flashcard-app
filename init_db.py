import sqlite3

def init_database():
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    try:
        # usersテーブルの作成
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
        ''')
        
        # 管理者ユーザーの作成（存在しない場合）
        cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, full_name, is_admin)
        VALUES ('admin', 'pbkdf2:sha256:600000$admin123$dummy_hash', '管理者', 1)
        ''')
        
        conn.commit()
        print("データベースの初期化が完了しました")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_database() 