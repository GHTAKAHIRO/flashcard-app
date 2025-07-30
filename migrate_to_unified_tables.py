#!/usr/bin/env python3
"""
既存のデータを統一されたテーブルに移行するスクリプト
"""

import sqlite3
import json
from datetime import datetime

def migrate_to_unified_tables():
    """既存のデータを統一されたテーブルに移行"""
    db_path = 'flashcards.db'
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        print("🔄 データ移行を開始します...")
        
        # 1. 入力問題の教材を統一テーブルに移行
        print("📚 入力問題教材を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO textbooks (id, name, subject, grade, publisher, description, study_type, is_active)
            SELECT id, name, subject, grade, publisher, description, 'input', TRUE
            FROM input_textbooks
        ''')
        
        # 2. 入力問題の単元を統一テーブルに移行
        print("📖 入力問題単元を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO units (id, textbook_id, name, chapter_number, description, is_active)
            SELECT id, textbook_id, name, chapter_number, description, TRUE
            FROM input_units
        ''')
        
        # 3. 入力問題を統一テーブルに移行
        print("❓ 入力問題を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO questions (
                id, unit_id, question_text, correct_answer, acceptable_answers, 
                answer_suffix, explanation, difficulty_level, image_name, 
                image_url, image_title, question_number, is_active
            )
            SELECT 
                id, unit_id, question, correct_answer, acceptable_answers,
                answer_suffix, explanation, difficulty_level, image_name,
                image_url, image_title, question_number, TRUE
            FROM input_questions
        ''')
        
        # 4. 選択問題の教材を統一テーブルに移行
        print("📚 選択問題教材を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO textbooks (id, name, subject, grade, publisher, description, study_type, is_active)
            SELECT 
                id + 10000,  -- 重複を避けるためIDをオフセット
                source || ' - ' || chapter_name, 
                '選択問題', 
                NULL, 
                NULL, 
                NULL, 
                'choice', 
                TRUE
            FROM choice_textbooks
        ''')
        
        # 5. 選択問題の単元を統一テーブルに移行
        print("📖 選択問題単元を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO units (id, textbook_id, name, chapter_number, description, is_active)
            SELECT 
                u.id + 10000,  -- 重複を避けるためIDをオフセット
                t.id + 10000,  -- 対応する教材のID
                u.name, 
                u.unit_number, 
                NULL, 
                TRUE
            FROM choice_units u
            JOIN choice_textbooks t ON u.textbook_id = t.id
        ''')
        
        # 6. 選択問題を統一テーブルに移行
        print("❓ 選択問題を移行中...")
        cursor.execute('''
            INSERT OR IGNORE INTO questions (
                id, unit_id, question_text, correct_answer, choices, 
                explanation, is_active
            )
            SELECT 
                q.id + 10000,  -- 重複を避けるためIDをオフセット
                u.id + 10000,  -- 対応する単元のID
                q.question, 
                q.correct_answer, 
                q.choices, 
                NULL, 
                TRUE
            FROM choice_questions q
            JOIN choice_units u ON q.unit_id = u.id
        ''')
        
        # 7. 教材割り当てを更新（assignment_typeカラムが存在する場合のみ）
        print("📋 教材割り当てを更新中...")
        try:
            cursor.execute('''
                UPDATE textbook_assignments 
                SET textbook_id = CASE 
                    WHEN assignment_type = 'input' THEN textbook_id
                    WHEN assignment_type = 'choice' THEN textbook_id + 10000
                END
                WHERE assignment_type = 'choice'
            ''')
        except sqlite3.OperationalError:
            print("⚠️  assignment_typeカラムが存在しないため、教材割り当ての更新をスキップします")
        
        conn.commit()
        print("✅ データ移行が完了しました！")
        
        # 移行結果を確認
        cursor.execute('SELECT COUNT(*) as count FROM textbooks')
        textbook_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM units')
        unit_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM questions')
        question_count = cursor.fetchone()['count']
        
        print(f"📊 移行結果:")
        print(f"   - 教材数: {textbook_count}")
        print(f"   - 単元数: {unit_count}")
        print(f"   - 問題数: {question_count}")
        
    except Exception as e:
        print(f"❌ データ移行エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_to_unified_tables() 