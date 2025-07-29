#!/usr/bin/env python3
"""
管理者ユーザーのパスワードをリセットするスクリプト
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

def reset_admin_password():
    """管理者ユーザーのパスワードをリセット"""
    db_path = os.getenv('DB_PATH', 'flashcards.db')
    
    print(f"📁 データベースパス: {db_path}")
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 管理者ユーザーの確認
        cursor.execute('SELECT id, username, is_admin, full_name FROM users WHERE username = ?', ('admin',))
        user = cursor.fetchone()
        
        if not user:
            print("❌ 管理者ユーザー 'admin' が見つかりません")
            return
        
        user_id, username, is_admin, full_name = user
        print(f"👤 管理者ユーザー情報: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}, 表示名={full_name}")
        
        if not is_admin:
            print("❌ ユーザー 'admin' に管理者権限がありません")
            return
        
        # パスワードをリセット
        new_password = 'admin'
        password_hash = generate_password_hash(new_password)
        
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        conn.commit()
        
        print(f"✅ 管理者ユーザー '{username}' のパスワードをリセットしました")
        print(f"🔑 新しいパスワード: {new_password}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_admin_password() 