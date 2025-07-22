#!/usr/bin/env python3
"""
SQLiteデータベース初期化スクリプト
"""

import sqlite3
import os
from datetime import datetime

def init_database():
    """データベースとテーブルを初期化"""
    db_path = 'flashcards.db'
    
    # データベースファイルが存在しない場合は作成
    if not os.path.exists(db_path):
        print(f"📁 データベースファイルを作成: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # テーブル作成
    tables = [
        # ユーザーテーブル
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # 学習ログテーブル
        """CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            stage INTEGER NOT NULL,
            mode TEXT NOT NULL,
            result TEXT NOT NULL,
            page_range TEXT,
            difficulty TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )""",
        
        # チャンク進捗テーブル
        """CREATE TABLE IF NOT EXISTS chunk_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            stage INTEGER NOT NULL,
            page_range TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            chunk_number INTEGER NOT NULL,
            is_completed BOOLEAN DEFAULT FALSE,
            is_passed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )""",
        
        # 画像テーブル
        """CREATE TABLE IF NOT EXISTS image (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            level TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # ユーザー設定テーブル
        """CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            page_range TEXT,
            difficulty TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )""",
        
        # 社会科テーブル
        """CREATE TABLE IF NOT EXISTS textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        """CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            textbook_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            unit_number INTEGER,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES textbooks (id)
        )""",
        
        """CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            textbook_id INTEGER NOT NULL,
            unit_id INTEGER,
            question_text TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            acceptable_answers TEXT,
            explanation TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES textbooks (id),
            FOREIGN KEY (unit_id) REFERENCES units (id)
        )""",
        
        # 語彙テーブル
        """CREATE TABLE IF NOT EXISTS vocabulary_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            chapter_name TEXT NOT NULL,
            chapter_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        """CREATE TABLE IF NOT EXISTS vocabulary_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            chunk_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chapter_id) REFERENCES vocabulary_chapters (id)
        )""",
        
        """CREATE TABLE IF NOT EXISTS vocabulary_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chapter_id INTEGER NOT NULL,
            chunk_number INTEGER NOT NULL,
            is_completed BOOLEAN DEFAULT FALSE,
            is_passed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (chapter_id) REFERENCES vocabulary_chapters (id)
        )"""
    ]
    
    try:
        cursor = conn.cursor()
        
        # テーブル作成
        for table_sql in tables:
            cursor.execute(table_sql)
            print(f"✅ テーブル作成完了")
        
        # インデックス作成
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_study_log_user_stage_mode ON study_log(user_id, stage, mode);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_composite ON study_log(user_id, stage, mode, card_id, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_page ON image(source, page_number);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_level ON image(source, level);",
            "CREATE INDEX IF NOT EXISTS idx_chunk_progress_user_source_stage ON chunk_progress(user_id, source, stage);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_card_result ON study_log(card_id, result, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_user_settings_user_source ON user_settings(user_id, source);",
            "CREATE INDEX IF NOT EXISTS idx_questions_textbook_unit ON questions(textbook_id, unit_id);",
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_words_chapter ON vocabulary_words(chapter_id, chunk_number);",
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_progress_user_chapter ON vocabulary_progress(user_id, chapter_id, chunk_number);"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            print(f"✅ インデックス作成完了")
        
        # デフォルト管理者ユーザーを作成（パスワード: admin123）
        from werkzeug.security import generate_password_hash
        
        admin_password_hash = generate_password_hash('admin123')
        cursor.execute('''
            INSERT OR IGNORE INTO users (student_number, username, email, password_hash, is_admin, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin', 'admin@example.com', admin_password_hash, True, True))
        
        conn.commit()
        print("✅ デフォルト管理者ユーザー作成完了")
        print("   ユーザー名: admin")
        print("   パスワード: admin123")
        
        print(f"🎉 データベース初期化完了: {db_path}")
        
    except Exception as e:
        print(f"❌ データベース初期化エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    init_database() 