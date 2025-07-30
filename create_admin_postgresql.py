#!/usr/bin/env python3
"""
PostgreSQLデータベースで管理者ユーザーを作成するスクリプト
"""

import psycopg2
import os
from werkzeug.security import generate_password_hash
from datetime import datetime
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv('dbname.env')

def create_admin_user():
    """管理者ユーザーを作成"""
    print("🔍 PostgreSQLデータベースに接続中...")
    
    try:
        # PostgreSQL接続
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        cursor = conn.cursor()
        print("✅ PostgreSQLデータベースに接続しました")
        
        # 既存のadminユーザーを確認
        cursor.execute('SELECT id, username, is_admin FROM users WHERE username = %s', ('admin',))
        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id, username, is_admin = existing_user
            print(f"👤 既存のユーザー: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}")
            
            if is_admin:
                print("✅ adminユーザーは既に存在し、管理者権限を持っています")
                
                # パスワードをリセット
                new_password = 'admin'
                password_hash = generate_password_hash(new_password)
                
                cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', (password_hash, user_id))
                conn.commit()
                
                print(f"✅ adminユーザーのパスワードをリセットしました")
                print(f"🔑 新しいパスワード: {new_password}")
                return
            else:
                print("⚠️ adminユーザーは存在しますが、管理者権限がありません")
                # 管理者権限を付与
                cursor.execute('UPDATE users SET is_admin = %s WHERE id = %s', (True, user_id))
                conn.commit()
                print("✅ adminユーザーに管理者権限を付与しました")
                return
        
        # adminユーザーが存在しない場合は新規作成
        print("👤 adminユーザーを作成します")
        
        username = 'admin'
        password = 'admin'
        password_hash = generate_password_hash(password)
        full_name = 'Administrator'
        is_admin = True
        created_at = datetime.now()
        
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, is_admin, created_at, last_login)
            VALUES (%s, %s, %s, %s, %s, NULL)
            RETURNING id
        ''', (username, password_hash, full_name, is_admin, created_at))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ adminユーザーを作成しました")
        print(f"👤 ユーザー情報: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}")
        print(f"🔑 パスワード: {password}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

def check_users():
    """全ユーザーを確認"""
    print("🔍 ユーザー一覧を取得中...")
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, username, is_admin, full_name, created_at FROM users ORDER BY id')
        users = cursor.fetchall()
        
        print("👥 ユーザー一覧:")
        print("ID | ユーザー名 | 管理者権限 | 表示名 | 作成日")
        print("-" * 70)
        
        for user in users:
            user_id, username, is_admin, full_name, created_at = user
            admin_status = "✅" if is_admin else "❌"
            print(f"{user_id:2d} | {username:10s} | {admin_status:8s} | {full_name or '':10s} | {created_at}")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_users()
    else:
        create_admin_user()
        print("\n" + "="*50)
        check_users() 