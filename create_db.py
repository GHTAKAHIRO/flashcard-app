import sqlite3
import os

def create_database():
    db_path = 'flashcards.db'
    
    if os.path.exists(db_path):
        print(f"データベースファイル {db_path} は既に存在します")
        return
    
    print(f"データベースファイル {db_path} を作成します")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 社会科関連のテーブルを作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS social_studies_textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT,
            publisher TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS social_studies_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            chapter_number INTEGER,
            description TEXT,
            textbook_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES social_studies_textbooks (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS social_studies_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            explanation TEXT,
            subject TEXT NOT NULL,
            difficulty TEXT DEFAULT 'normal',
            textbook_id INTEGER,
            unit_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES social_studies_textbooks (id),
            FOREIGN KEY (unit_id) REFERENCES social_studies_units (id)
        )
    ''')
    
    # ユーザーテーブルも作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # 管理者ユーザーを作成
    from werkzeug.security import generate_password_hash
    admin_password = generate_password_hash('admin')
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash, is_admin, full_name)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', 'admin@example.com', admin_password, True, '管理者'))
    
    conn.commit()
    conn.close()
    
    print("データベースの作成が完了しました")
    print("管理者アカウント: admin / admin")

if __name__ == "__main__":
    create_database() 