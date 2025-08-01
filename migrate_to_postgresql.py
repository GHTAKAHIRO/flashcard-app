#!/usr/bin/env python3
"""
SQLiteからPostgreSQLへのデータ移行スクリプト
"""

import sqlite3
import psycopg2
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

def migrate_to_postgresql():
    """SQLiteからPostgreSQLへのデータ移行"""
    load_dotenv(dotenv_path='dbname.env')
    
    # 環境変数の確認
    db_type = os.getenv('DB_TYPE', 'sqlite')
    if db_type != 'postgresql':
        print("❌ DB_TYPEがpostgresqlに設定されていません")
        return False
    
    # PostgreSQL接続情報
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_host, db_port, db_name, db_user, db_password]):
        print("❌ PostgreSQL接続情報が不完全です")
        return False
    
    # SQLiteファイルの確認
    sqlite_path = 'flashcards.db'
    if not os.path.exists(sqlite_path):
        print("❌ SQLiteファイルが見つかりません")
        return False
    
    try:
        # SQLite接続
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        
        # PostgreSQL接続
        pg_conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=10
        )
        
        print("✅ データベース接続完了")
        
        # ユーザーデータの移行
        print("👥 ユーザーデータを移行中...")
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # ユーザーテーブルの作成
        pg_cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
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
            )
        ''')
        
        # 既存のユーザーデータを取得
        sqlite_cursor.execute('SELECT * FROM users')
        users = sqlite_cursor.fetchall()
        
        for user in users:
            # ユーザーが既に存在するかチェック
            pg_cursor.execute('SELECT id FROM users WHERE username = %s', (user['username'],))
            if not pg_cursor.fetchone():
                # boolean型の変換
                is_admin = bool(user['is_admin']) if user['is_admin'] is not None else False
                is_active = bool(user['is_active']) if user['is_active'] is not None else True
                
                pg_cursor.execute('''
                    INSERT INTO users (username, full_name, email, password_hash, is_admin, is_active, grade, last_login, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    user['username'],
                    user['full_name'],
                    user['email'],
                    user['password_hash'],
                    is_admin,
                    is_active,
                    user['grade'],
                    user['last_login'],
                    user['created_at']
                ))
                print(f"✅ ユーザー '{user['username']}' を移行しました")
            else:
                print(f"⚠️  ユーザー '{user['username']}' は既に存在します")
        
        # 教材データの移行
        print("📚 教材データを移行中...")
        
        # input_textbooksテーブルの作成
        pg_cursor.execute('''
            CREATE TABLE IF NOT EXISTS input_textbooks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                question_types TEXT DEFAULT '["input"]',
                subject VARCHAR(100) DEFAULT '地理',
                grade VARCHAR(50) DEFAULT '高校',
                publisher VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # input_unitsテーブルの作成
        pg_cursor.execute('''
            CREATE TABLE IF NOT EXISTS input_units (
                id SERIAL PRIMARY KEY,
                textbook_id INTEGER,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                unit_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (textbook_id) REFERENCES input_textbooks (id)
            )
        ''')
        
        # input_questionsテーブルの作成
        pg_cursor.execute('''
            CREATE TABLE IF NOT EXISTS input_questions (
                id SERIAL PRIMARY KEY,
                unit_id INTEGER,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                image_path TEXT,
                question_type VARCHAR(50) DEFAULT 'input',
                question_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES input_units (id)
            )
        ''')
        
        # 教材データの移行
        sqlite_cursor.execute('SELECT * FROM input_textbooks')
        textbooks = sqlite_cursor.fetchall()
        
        for textbook in textbooks:
            pg_cursor.execute('SELECT id FROM input_textbooks WHERE title = %s', (textbook['name'],))
            if not pg_cursor.fetchone():
                pg_cursor.execute('''
                    INSERT INTO input_textbooks (title, description, subject, grade, publisher, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (
                    textbook['name'],
                    textbook['description'],
                    textbook['subject'],
                    textbook['grade'],
                    textbook['publisher'],
                    textbook['created_at']
                ))
                pg_cursor.execute('SELECT lastval()')
                new_textbook_id = pg_cursor.fetchone()[0]
                print(f"✅ 教材 '{textbook['name']}' を移行しました (ID: {new_textbook_id})")
        
        # 単元データの移行
        sqlite_cursor.execute('SELECT * FROM input_units')
        units = sqlite_cursor.fetchall()
        
        for unit in units:
            pg_cursor.execute('SELECT id FROM input_units WHERE title = %s AND textbook_id = %s', 
                            (unit['name'], unit['textbook_id']))
            if not pg_cursor.fetchone():
                pg_cursor.execute('''
                    INSERT INTO input_units (textbook_id, title, description, unit_number, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    unit['textbook_id'],
                    unit['name'],
                    unit['description'],
                    unit['chapter_number'],
                    unit['created_at']
                ))
                print(f"✅ 単元 '{unit['name']}' を移行しました")
        
        # 問題データの移行
        sqlite_cursor.execute('SELECT * FROM input_questions')
        questions = sqlite_cursor.fetchall()
        
        for question in questions:
            pg_cursor.execute('SELECT id FROM input_questions WHERE question_text = %s AND unit_id = %s', 
                            (question['question'], question['unit_id']))
            if not pg_cursor.fetchone():
                pg_cursor.execute('''
                    INSERT INTO input_questions (unit_id, question_text, correct_answer, explanation, image_path, question_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (
                    question['unit_id'],
                    question['question'],
                    question['correct_answer'],
                    question['explanation'],
                    question['image_url'],
                    'input',
                    question['created_at']
                ))
                print(f"✅ 問題 '{question['question'][:30]}...' を移行しました")
        
        # 変更をコミット
        pg_conn.commit()
        print("✅ データ移行が完了しました")
        
        # 接続を閉じる
        sqlite_conn.close()
        pg_conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ データ移行エラー: {e}")
        return False

if __name__ == '__main__':
    migrate_to_postgresql() 