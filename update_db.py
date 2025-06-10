import sqlite3

def update_database():
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    try:
        # テーブルの存在確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            # usersテーブルが存在しない場合は新規作成
            cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
            ''')
        else:
            # 既存のテーブルにカラムを追加
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
            except sqlite3.OperationalError:
                print("full_nameカラムは既に存在します")
            
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
            except sqlite3.OperationalError:
                print("is_adminカラムは既に存在します")
        
        # 管理者ユーザーの作成（存在しない場合）
        cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, full_name, is_admin)
        VALUES ('admin', 'pbkdf2:sha256:600000$admin123$dummy_hash', '管理者', 1)
        ''')
        
        conn.commit()
        print("データベースの更新が完了しました")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    update_database() 