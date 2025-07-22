#!/usr/bin/env python3
"""
adminユーザーの状態を確認するスクリプト
"""

import sqlite3

def check_admin_user():
    """adminユーザーの状態を確認"""
    db_path = 'flashcards.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # adminユーザーの情報を取得
        cursor.execute("SELECT username, is_admin, is_active, full_name FROM users WHERE username='admin'")
        user = cursor.fetchone()
        
        if user:
            print(f"✅ adminユーザーが見つかりました:")
            print(f"   ユーザー名: {user[0]}")
            print(f"   管理者権限: {user[1]}")
            print(f"   アクティブ: {user[2]}")
            print(f"   フルネーム: {user[3]}")
        else:
            print("❌ adminユーザーが見つかりません")
            
        # 全ユーザー数を確認
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"\n📊 全ユーザー数: {total_users}")
        
        # 管理者ユーザー数を確認
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        admin_users = cursor.fetchone()[0]
        print(f"👑 管理者ユーザー数: {admin_users}")
        
        # 全ユーザーの詳細情報を表示
        print(f"\n📋 全ユーザー一覧:")
        cursor.execute("SELECT username, is_admin, is_active, full_name FROM users")
        all_users = cursor.fetchall()
        
        for user in all_users:
            print(f"   ユーザー名: {user[0]}")
            print(f"   管理者権限: {user[1]}")
            print(f"   アクティブ: {user[2]}")
            print(f"   フルネーム: {user[3]}")
            print("   ---")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == '__main__':
    check_admin_user() 