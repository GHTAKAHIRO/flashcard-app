#!/usr/bin/env python3
"""
テーブル作成とエラー修正スクリプト
"""

import sqlite3
import os

def fix_database():
    """データベースの修正とテーブル作成"""
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # 教材割り当てテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS textbook_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                textbook_id INTEGER NOT NULL,
                assignment_type TEXT NOT NULL,
                units TEXT,
                chunks TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                assigned_by INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        print("✅ textbook_assignments テーブル作成完了")
        
        # 教材割り当て詳細テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                unit_id INTEGER,
                chunk_start INTEGER,
                chunk_end INTEGER,
                difficulty_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ assignment_details テーブル作成完了")
        
        # インデックス作成
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_textbook_assignments_user ON textbook_assignments(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_textbook_assignments_active ON textbook_assignments(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_assignment_details_assignment ON assignment_details(assignment_id);"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        print("✅ インデックス作成完了")
        
        # テストデータの挿入（オプション）
        # cursor.execute('''
        #     INSERT INTO textbook_assignments (user_id, textbook_id, assignment_type, assigned_by)
        #     VALUES (1, 1, 'input', 1)
        # ''')
        
        conn.commit()
        print("🎉 データベース修正が完了しました")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database() 