#!/usr/bin/env python3
"""
管理者ユーザーを作成するスクリプト
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_admin_user():
    """管理者ユーザーを作成"""
    db_path = os.getenv('DB_PATH', 'flashcards.db')
    
    print(f"📁 データベースパス: {db_path}")
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 既存のadminユーザーを確認
        cursor.execute('SELECT id, username, is_admin FROM users WHERE username = ?', ('admin',))
        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id, username, is_admin = existing_user
            print(f"👤 既存のユーザー: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}")
            
            if is_admin:
                print("✅ adminユーザーは既に存在し、管理者権限を持っています")
                
                # パスワードをリセット
                new_password = 'admin'
                password_hash = generate_password_hash(new_password)
                
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
                conn.commit()
                
                print(f"✅ adminユーザーのパスワードをリセットしました")
                print(f"🔑 新しいパスワード: {new_password}")
                return
            else:
                print("⚠️ adminユーザーは存在しますが、管理者権限がありません")
                # 管理者権限を付与
                cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (True, user_id))
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
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, is_admin, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, NULL)
        ''', (username, password_hash, full_name, is_admin, created_at))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        print(f"✅ adminユーザーを作成しました")
        print(f"👤 ユーザー情報: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}")
        print(f"🔑 パスワード: {password}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

def check_users():
    """全ユーザーを確認"""
    db_path = os.getenv('DB_PATH', 'flashcards.db')
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
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
        conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_users()
    else:
        create_admin_user()
        print("\n" + "="*50)
        check_users() 