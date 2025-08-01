#!/usr/bin/env python3
"""
本番環境のPostgreSQLデータベース接続テスト
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def test_production_db_connection():
    """本番環境のデータベース接続をテスト"""
    
    print("🔍 本番環境データベース接続テスト")
    print("=" * 50)
    
    # 環境変数設定
    DB_HOST = "flashcards.c98oe62ei7dh.ap-northeast-1.rds.amazonaws.com"
    DB_PORT = 5432
    DB_NAME = "dbname"
    DB_USER = "takahiro"
    DB_PASSWORD = "hirotan0908"
    
    print(f"📡 接続先: {DB_HOST}:{DB_PORT}")
    print(f"🗄️ データベース: {DB_NAME}")
    print(f"👤 ユーザー: {DB_USER}")
    
    try:
        # PostgreSQL接続テスト
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        print("✅ PostgreSQL接続成功")
        
        # テーブル一覧を取得
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            
            print(f"\n📋 テーブル一覧 ({len(tables)}件):")
            for table in tables:
                print(f"  - {table['table_name']}")
            
            # usersテーブルの確認
            if any(table['table_name'] == 'users' for table in tables):
                cur.execute("SELECT COUNT(*) as user_count FROM users")
                user_count = cur.fetchone()['user_count']
                print(f"\n👥 ユーザー数: {user_count}")
                
                if user_count > 0:
                    cur.execute("""
                        SELECT id, username, is_admin, created_at 
                        FROM users 
                        ORDER BY id DESC 
                        LIMIT 5
                    """)
                    users = cur.fetchall()
                    print("\n📊 最新ユーザー（上位5件）:")
                    for user in users:
                        admin_status = "✅" if user['is_admin'] else "❌"
                        print(f"  - ID: {user['id']}, ユーザー名: {user['username']}, 管理者: {admin_status}, 作成日: {user['created_at']}")
            else:
                print("\n❌ usersテーブルが存在しません")
        
        conn.close()
        print("\n✅ データベース接続テスト完了")
        
    except Exception as e:
        print(f"\n❌ 接続エラー: {e}")
        print("\n🔧 トラブルシューティング:")
        print("1. ネットワーク接続を確認")
        print("2. データベース認証情報を確認")
        print("3. ファイアウォール設定を確認")
        print("4. AWS RDSの状態を確認")

if __name__ == "__main__":
    test_production_db_connection() 