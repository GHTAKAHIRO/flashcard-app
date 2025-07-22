#!/usr/bin/env python3
"""
ユーザー情報を確認するスクリプト
"""

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def check_user_info():
    """ユーザー情報を確認"""
    db_path = 'flashcards.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # adminユーザーの情報を取得
        cursor.execute("SELECT id, username, password_hash, is_admin, full_name FROM users WHERE username='admin'")
        user = cursor.fetchone()
        
        if user:
            print(f"✅ adminユーザーが見つかりました:")
            print(f"   ID: {user[0]}")
            print(f"   ユーザー名: {user[1]}")
            print(f"   パスワードハッシュ: {user[2]}")
            print(f"   管理者権限: {user[3]}")
            print(f"   フルネーム: {user[4]}")
            
            # パスワードハッシュの検証
            test_password = "admin123"
            if check_password_hash(user[2], test_password):
                print(f"✅ パスワード '{test_password}' は正しいです")
            else:
                print(f"❌ パスワード '{test_password}' は間違っています")
                
                # 新しいハッシュを生成
                new_hash = generate_password_hash(test_password)
                print(f"🔄 新しいハッシュを生成: {new_hash}")
                
                # データベースを更新
                cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, 'admin'))
                conn.commit()
                print("✅ パスワードハッシュを更新しました")
        else:
            print("❌ adminユーザーが見つかりません")
            
        # 全ユーザー数を確認
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        print(f"\n📊 全ユーザー数: {total_users}")
        
        # 全ユーザーの詳細情報を表示
        print(f"\n📋 全ユーザー一覧:")
        cursor.execute("SELECT username, is_admin, full_name FROM users")
        all_users = cursor.fetchall()
        
        for user in all_users:
            print(f"   ユーザー名: {user[0]}")
            print(f"   管理者権限: {user[1]}")
            print(f"   フルネーム: {user[2]}")
            print("   ---")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == '__main__':
    check_user_info() 