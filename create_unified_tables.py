#!/usr/bin/env python3
"""
統一された教材データ構造を作成するスクリプト
"""

import sqlite3
import os

def create_unified_database():
    """統一された教材データ構造を作成"""
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # 統一された教材テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS textbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT,
                publisher TEXT,
                description TEXT,
                study_type TEXT DEFAULT 'both',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ textbooks テーブル作成完了")
        
        # 統一された単元テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                textbook_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                chapter_number INTEGER,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (textbook_id) REFERENCES textbooks (id)
            )
        ''')
        print("✅ units テーブル作成完了")
        
        # 統一された問題テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                choices TEXT,
                acceptable_answers TEXT,
                answer_suffix TEXT,
                explanation TEXT,
                difficulty_level TEXT,
                image_name TEXT,
                image_url TEXT,
                image_title TEXT,
                question_number INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES units (id)
            )
        ''')
        print("✅ questions テーブル作成完了")
        
        # 学習セッションテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                textbook_id INTEGER NOT NULL,
                unit_id INTEGER,
                study_type TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                completed BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (textbook_id) REFERENCES textbooks (id),
                FOREIGN KEY (unit_id) REFERENCES units (id)
            )
        ''')
        print("✅ study_sessions テーブル作成完了")
        
        # 統一された学習ログテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN NOT NULL,
                study_type TEXT NOT NULL,
                response_time INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES study_sessions (id),
                FOREIGN KEY (question_id) REFERENCES questions (id)
            )
        ''')
        print("✅ study_logs テーブル作成完了")
        
        # 教材割り当てテーブルを更新
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS textbook_assignments_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                textbook_id INTEGER NOT NULL,
                study_type TEXT DEFAULT 'both',
                units TEXT,
                chunks TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                assigned_by INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (textbook_id) REFERENCES textbooks (id),
                FOREIGN KEY (assigned_by) REFERENCES users (id)
            )
        ''')
        print("✅ textbook_assignments_new テーブル作成完了")
        
        # インデックス作成
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_textbooks_subject ON textbooks(subject);",
            "CREATE INDEX IF NOT EXISTS idx_textbooks_active ON textbooks(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_units_textbook ON units(textbook_id);",
            "CREATE INDEX IF NOT EXISTS idx_units_active ON units(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_questions_unit ON questions(unit_id);",
            "CREATE INDEX IF NOT EXISTS idx_questions_active ON questions(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_study_sessions_user ON study_sessions(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_study_sessions_textbook ON study_sessions(textbook_id);",
            "CREATE INDEX IF NOT EXISTS idx_study_logs_session ON study_logs(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_study_logs_question ON study_logs(question_id);"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        print("✅ インデックス作成完了")
        
        # サンプルデータの挿入（テスト用）
        cursor.execute('''
            INSERT OR IGNORE INTO textbooks (name, subject, grade, publisher, description, study_type)
            VALUES ('数学基礎', 'math', 'senior1', '数研出版', '高校数学の基礎を学ぶ教材', 'both')
        ''')
        
        textbook_id = cursor.lastrowid
        if textbook_id == 0:
            cursor.execute('SELECT id FROM textbooks WHERE name = ?', ('数学基礎',))
            textbook_id = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT OR IGNORE INTO units (textbook_id, name, chapter_number, description)
            VALUES (?, '数と式', 1, '数と式の基本概念')
        ''', (textbook_id,))
        
        print("✅ サンプルデータ挿入完了")
        
        conn.commit()
        print("🎉 統一された教材データ構造の作成が完了しました")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_unified_database() 