#!/usr/bin/env python3
"""
SQLiteデータベース初期化スクリプト
"""

import sqlite3
import os
from datetime import datetime

def init_database():
    print("init_database called")
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
            username TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            grade TEXT,
            last_login TIMESTAMP,
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
        
        # 入力問題テーブル
        """CREATE TABLE IF NOT EXISTS input_textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT,
            publisher TEXT,
            description TEXT,
            wasabi_folder_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        """CREATE TABLE IF NOT EXISTS input_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            textbook_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            chapter_number INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES input_textbooks (id)
        )""",
        
        """CREATE TABLE IF NOT EXISTS input_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            textbook_id INTEGER NOT NULL,
            unit_id INTEGER,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            acceptable_answers TEXT,
            answer_suffix TEXT,
            explanation TEXT,
            difficulty_level TEXT,
            image_name TEXT,
            image_url TEXT,
            image_title TEXT,
            question_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES input_textbooks (id),
            FOREIGN KEY (unit_id) REFERENCES input_units (id)
        )""",
        # 入力問題学習ログテーブル
        """CREATE TABLE IF NOT EXISTS input_study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT,
            is_correct BOOLEAN,
            subject TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (question_id) REFERENCES input_questions (id)
        )""",
        
        # 選択問題テーブル
        """CREATE TABLE IF NOT EXISTS choice_textbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            chapter_name TEXT NOT NULL,
            chapter_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        """CREATE TABLE IF NOT EXISTS choice_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            textbook_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            unit_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (textbook_id) REFERENCES choice_textbooks (id)
        )""",
        
        """CREATE TABLE IF NOT EXISTS choice_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            choices TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES choice_units (id)
        )""",
        
        """CREATE TABLE IF NOT EXISTS choice_study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN NOT NULL,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (question_id) REFERENCES choice_questions (id)
        )""",
        
        # 教材割り当てテーブル
        """CREATE TABLE IF NOT EXISTS textbook_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            textbook_id INTEGER NOT NULL,
            assignment_type TEXT NOT NULL,  -- 'input' or 'choice'
            units TEXT,  -- JSON形式で選択された単元ID
            chunks TEXT,  -- JSON形式で選択されたチャンク情報
            is_active BOOLEAN DEFAULT TRUE,
            assigned_by INTEGER NOT NULL,  -- 割り当てた管理者のID
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assigned_by) REFERENCES users (id)
        )""",
        
        # 教材割り当て詳細テーブル
        """CREATE TABLE IF NOT EXISTS assignment_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            unit_id INTEGER,
            chunk_start INTEGER,
            chunk_end INTEGER,
            difficulty_level TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES textbook_assignments (id)
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
            "CREATE INDEX IF NOT EXISTS idx_questions_textbook_unit ON input_questions(textbook_id, unit_id);",
            "CREATE INDEX IF NOT EXISTS idx_choice_units_textbook ON choice_units(textbook_id, unit_number);",
            "CREATE INDEX IF NOT EXISTS idx_choice_questions_unit ON choice_questions(unit_id);",
            "CREATE INDEX IF NOT EXISTS idx_choice_study_log_user_question ON choice_study_log(user_id, question_id);",
            "CREATE INDEX IF NOT EXISTS idx_choice_study_log_user ON choice_study_log(user_id, answered_at);"
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
    print("__main__ section called")
    init_database() 