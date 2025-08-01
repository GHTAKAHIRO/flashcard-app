#!/usr/bin/env python3
"""
PostgreSQLデータベースを手動で初期化するスクリプト
"""

import psycopg2
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

def init_postgresql():
    """PostgreSQLデータベースを手動で初期化"""
    load_dotenv(dotenv_path='dbname.env')
    
    # PostgreSQL接続情報
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_host, db_port, db_name, db_user, db_password]):
        print("❌ PostgreSQL接続情報が不完全です")
        return False
    
    try:
        # PostgreSQL接続
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=10
        )
        cursor = conn.cursor()
        
        print("🔄 PostgreSQLデータベースを初期化中...")
        
        # テーブル作成
        tables = [
            # ユーザーテーブル
            '''CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255),
                email VARCHAR(255),
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                grade VARCHAR(50) DEFAULT '一般',
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 学習ログテーブル
            '''CREATE TABLE IF NOT EXISTS study_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                stage INTEGER NOT NULL,
                mode TEXT NOT NULL,
                result TEXT NOT NULL,
                page_range TEXT,
                difficulty TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # チャンク進捗テーブル
            '''CREATE TABLE IF NOT EXISTS chunk_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                stage INTEGER NOT NULL,
                page_range TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                chunk_number INTEGER NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                is_passed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 画像テーブル
            '''CREATE TABLE IF NOT EXISTS image (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                level TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # ユーザー設定テーブル
            '''CREATE TABLE IF NOT EXISTS user_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                page_range TEXT,
                difficulty TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 入力問題テーブル
            '''CREATE TABLE IF NOT EXISTS input_textbooks (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT,
                publisher TEXT,
                description TEXT,
                wasabi_folder_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS input_units (
                id SERIAL PRIMARY KEY,
                textbook_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                chapter_number INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS input_questions (
                id SERIAL PRIMARY KEY,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 入力問題学習ログテーブル
            '''CREATE TABLE IF NOT EXISTS input_study_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT,
                is_correct BOOLEAN,
                subject TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 選択問題テーブル
            '''CREATE TABLE IF NOT EXISTS choice_textbooks (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                chapter_name TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS choice_units (
                id SERIAL PRIMARY KEY,
                textbook_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                unit_number INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS choice_questions (
                id SERIAL PRIMARY KEY,
                unit_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                choices TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS choice_study_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN NOT NULL,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 統一された教材テーブル
            '''CREATE TABLE IF NOT EXISTS textbooks (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT,
                publisher TEXT,
                description TEXT,
                study_type TEXT DEFAULT 'both',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS units (
                id SERIAL PRIMARY KEY,
                textbook_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                unit_number INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                unit_id INTEGER NOT NULL,
                question TEXT NOT NULL,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 学習セッションテーブル
            '''CREATE TABLE IF NOT EXISTS study_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                textbook_id INTEGER NOT NULL,
                unit_id INTEGER,
                study_type TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                completed BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 統一された学習ログテーブル
            '''CREATE TABLE IF NOT EXISTS study_logs (
                id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN NOT NULL,
                study_type TEXT NOT NULL,
                response_time INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # 教材割り当てテーブル
            '''CREATE TABLE IF NOT EXISTS textbook_assignments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                textbook_id INTEGER NOT NULL,
                study_type TEXT DEFAULT 'both',
                units TEXT,
                chunks TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                assigned_by INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )''',
            
            # 教材割り当て詳細テーブル
            '''CREATE TABLE IF NOT EXISTS assignment_details (
                id SERIAL PRIMARY KEY,
                assignment_id INTEGER NOT NULL,
                unit_id INTEGER,
                chunk_start INTEGER,
                chunk_end INTEGER,
                difficulty_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        
        # テーブル作成
        for i, table_sql in enumerate(tables, 1):
            try:
                cursor.execute(table_sql)
                print(f"✅ テーブル {i}/{len(tables)} 作成完了")
            except Exception as e:
                print(f"❌ テーブル {i}/{len(tables)} 作成エラー: {e}")
        
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
        
        print("\n🔄 インデックスを作成中...")
        for i, index_sql in enumerate(indexes, 1):
            try:
                cursor.execute(index_sql)
                print(f"✅ インデックス {i}/{len(indexes)} 作成完了")
            except Exception as e:
                print(f"❌ インデックス {i}/{len(indexes)} 作成エラー: {e}")
        
        # 管理者ユーザーを作成
        print("\n👤 管理者ユーザーを作成中...")
        admin_password_hash = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        ''', ('admin', 'admin@example.com', admin_password_hash, True, '管理者', datetime.now()))
        
        # 初期データを作成
        print("\n📚 初期データを作成中...")
        
        # 初期教材を作成
        cursor.execute('''
            INSERT INTO input_textbooks (name, subject, grade, publisher, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        ''', ('ファイナルステージ', '地理', '高校', '出版社名', '地理の総合問題集', datetime.now()))
        
        result = cursor.fetchone()
        if result:
            textbook_id = result[0]
            print(f"✅ 初期教材を作成しました: ID={textbook_id}")
            
            # 初期単元を作成
            units = [
                ('日本の自然環境', 1, '日本の地形・気候・自然災害について'),
                ('日本の産業', 2, '日本の農業・工業・サービス業について'),
                ('日本の人口・都市', 3, '日本の人口動態と都市問題について'),
                ('世界の自然環境', 4, '世界の地形・気候・自然環境について'),
                ('世界の産業・経済', 5, '世界の産業構造と経済について')
            ]
            
            for unit_name, chapter_num, description in units:
                cursor.execute('''
                    INSERT INTO input_units (textbook_id, name, chapter_number, description, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                ''', (textbook_id, unit_name, chapter_num, description, datetime.now()))
            
            print(f"✅ {len(units)}個の初期単元を作成しました")
            
            # サンプル問題を作成
            sample_questions = [
                ('日本の最高峰は？', '富士山', '日本一高い山は富士山です。', 'basic'),
                ('日本の首都は？', '東京', '日本の首都は東京です。', 'basic'),
                ('日本で最も人口が多い都道府県は？', '東京都', '東京都が最も人口が多いです。', 'normal'),
                ('日本の気候区分で最も多いのは？', '温帯', '日本は温帯気候が最も広く分布しています。', 'normal'),
                ('日本の主要な産業は？', '自動車産業', '自動車産業は日本の主要な産業の一つです。', 'advanced')
            ]
            
            for question, answer, explanation, difficulty in sample_questions:
                cursor.execute('''
                    INSERT INTO input_questions 
                    (subject, textbook_id, question, correct_answer, explanation, difficulty_level, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                ''', ('地理', textbook_id, question, answer, explanation, difficulty, datetime.now()))
            
            print(f"✅ {len(sample_questions)}個のサンプル問題を作成しました")
        
        conn.commit()
        print("\n🎉 PostgreSQLデータベース初期化完了")
        
        # 統計情報を表示
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM input_textbooks')
        textbook_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM input_units')
        unit_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM input_questions')
        question_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM study_log')
        study_log_count = cursor.fetchone()[0]
        
        print(f"\n📊 初期化後のデータ統計:")
        print(f"   ユーザー数: {user_count}")
        print(f"   教材数: {textbook_count}")
        print(f"   単元数: {unit_count}")
        print(f"   問題数: {question_count}")
        print(f"   学習ログ数: {study_log_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL初期化エラー: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    init_postgresql() 