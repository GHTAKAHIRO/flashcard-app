#!/usr/bin/env python3
"""
PostgreSQLデータベースのテーブル状態を確認するスクリプト
"""

import psycopg2
import os
from dotenv import load_dotenv

def check_postgresql_tables():
    """PostgreSQLデータベースのテーブル状態を確認"""
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
        
        print("🔍 PostgreSQLデータベースのテーブル状態を確認中...")
        
        # テーブル一覧を取得
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print(f"📊 存在するテーブル数: {len(tables)}")
        print("📋 テーブル一覧:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # 重要なテーブルの存在確認
        important_tables = [
            'users', 'study_log', 'input_textbooks', 'input_units', 
            'input_questions', 'choice_textbooks', 'choice_units', 
            'choice_questions', 'choice_study_log', 'input_study_log'
        ]
        
        print("\n🔍 重要なテーブルの存在確認:")
        for table_name in important_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (table_name,))
            exists = cursor.fetchone()[0]
            status = "✅" if exists else "❌"
            print(f"   {status} {table_name}")
        
        # study_logテーブルの詳細確認
        print("\n🔍 study_logテーブルの詳細確認:")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'study_log'
            )
        """)
        study_log_exists = cursor.fetchone()[0]
        
        if study_log_exists:
            # テーブル構造を確認
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'study_log'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            
            print("   📋 study_logテーブルの構造:")
            for column in columns:
                nullable = "NULL" if column[2] == "YES" else "NOT NULL"
                print(f"      - {column[0]}: {column[1]} ({nullable})")
            
            # レコード数を確認
            cursor.execute("SELECT COUNT(*) FROM study_log")
            count = cursor.fetchone()[0]
            print(f"   📊 レコード数: {count}")
        else:
            print("   ❌ study_logテーブルが存在しません")
        
        # ユーザーテーブルの確認
        print("\n🔍 usersテーブルの確認:")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        users_exists = cursor.fetchone()[0]
        
        if users_exists:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"   📊 ユーザー数: {user_count}")
            
            if user_count > 0:
                cursor.execute("SELECT username, is_admin FROM users LIMIT 5")
                users = cursor.fetchall()
                print("   👥 ユーザー一覧（上位5件）:")
                for user in users:
                    admin_status = "管理者" if user[1] else "一般"
                    print(f"      - {user[0]} ({admin_status})")
        else:
            print("   ❌ usersテーブルが存在しません")
        
        conn.close()
        print("\n✅ PostgreSQLデータベース確認完了")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL確認エラー: {e}")
        return False

if __name__ == '__main__':
    check_postgresql_tables() 