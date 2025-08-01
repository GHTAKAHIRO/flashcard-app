#!/usr/bin/env python3
"""
PostgreSQL接続テストスクリプト
"""

import psycopg2
import os
from dotenv import load_dotenv

def test_postgresql_connection():
    """PostgreSQL接続をテスト"""
    load_dotenv(dotenv_path='dbname.env')
    
    # 環境変数の確認
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    print("🔍 PostgreSQL接続情報:")
    print(f"Host: {db_host}")
    print(f"Port: {db_port}")
    print(f"Database: {db_name}")
    print(f"User: {db_user}")
    print(f"Password: {'*' * len(db_password) if db_password else 'Not set'}")
    
    if not all([db_host, db_port, db_name, db_user, db_password]):
        print("❌ 接続情報が不完全です")
        return False
    
    try:
        # PostgreSQL接続
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        
        print("✅ PostgreSQL接続成功")
        
        # カーソルを作成
        cursor = conn.cursor()
        
        # データベースバージョンを確認
        cursor.execute('SELECT version()')
        version = cursor.fetchone()
        print(f"📊 PostgreSQLバージョン: {version[0]}")
        
        # テーブル一覧を確認
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        
        if tables:
            print("📋 既存のテーブル:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("📋 テーブルが存在しません")
        
        # 接続を閉じる
        cursor.close()
        conn.close()
        
        print("✅ 接続テスト完了")
        return True
        
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        return False

if __name__ == '__main__':
    test_postgresql_connection() 