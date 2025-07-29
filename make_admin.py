#!/usr/bin/env python3
"""
ユーザーを管理者に変更するスクリプト
"""

import sqlite3
import os
from datetime import datetime

def make_user_admin(username):
    """指定されたユーザーを管理者に変更"""
    db_path = os.getenv('DB_PATH', 'flashcards.db')
    
    print(f"📁 データベースパス: {db_path}")
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # ユーザーの存在確認
        cursor.execute('SELECT id, username, is_admin, full_name FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ ユーザー '{username}' が見つかりません")
            return
        
        user_id, username, is_admin, full_name = user
        print(f"👤 ユーザー情報: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}, 表示名={full_name}")
        
        if is_admin:
            print(f"✅ ユーザー '{username}' は既に管理者権限を持っています")
            return
        
        # 管理者権限を付与
        cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (True, user_id))
        conn.commit()
        
        print(f"✅ ユーザー '{username}' に管理者権限を付与しました")
        
        # 更新後の確認
        cursor.execute('SELECT id, username, is_admin, full_name FROM users WHERE username = ?', (username,))
        updated_user = cursor.fetchone()
        print(f"👤 更新後のユーザー情報: ID={updated_user[0]}, ユーザー名={updated_user[1]}, 管理者権限={updated_user[2]}, 表示名={updated_user[3]}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()

def list_users():
    """全ユーザーの一覧を表示"""
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
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_users()
        else:
            username = sys.argv[1]
            make_user_admin(username)
    else:
        print("使用方法:")
        print("  python make_admin.py <ユーザー名>  # 指定したユーザーを管理者に変更")
        print("  python make_admin.py list          # 全ユーザーの一覧を表示")
        print("\n例:")
        print("  python make_admin.py 123456")
        print("  python make_admin.py list") 