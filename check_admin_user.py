import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

def check_admin_user():
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # テーブル一覧を確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("データベース内のテーブル:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # usersテーブルの構造を確認
        cursor.execute("PRAGMA table_info(users);")
        columns = cursor.fetchall()
        print("\nusersテーブルの構造:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # adminユーザーを検索
        cursor.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE username = 'admin';")
        admin_user = cursor.fetchone()
        
        if admin_user:
            print(f"\nadminユーザーが見つかりました:")
            print(f"  ID: {admin_user[0]}")
            print(f"  Username: {admin_user[1]}")
            print(f"  Password Hash: {admin_user[2]}")
            print(f"  Full Name: {admin_user[3]}")
            print(f"  Is Admin: {admin_user[4]}")
            
            # パスワードハッシュの長さを確認
            hash_length = len(admin_user[2]) if admin_user[2] else 0
            print(f"  パスワードハッシュの長さ: {hash_length}")
            
            # 一般的なパスワードでテスト
            test_passwords = ['admin', 'password', '123456', 'admin123']
            for test_pwd in test_passwords:
                if admin_user[2] and check_password_hash(admin_user[2], test_pwd):
                    print(f"  テストパスワード '{test_pwd}' が一致しました！")
                    break
            else:
                print("  テストパスワードでは一致しませんでした")
        else:
            print("\nadminユーザーが見つかりませんでした")
            
            # 全ユーザーを表示
            cursor.execute("SELECT id, username, full_name, is_admin FROM users;")
            users = cursor.fetchall()
            print("\n登録されているユーザー:")
            for user in users:
                print(f"  - ID: {user[0]}, Username: {user[1]}, Name: {user[2]}, Admin: {user[3]}")
        
        conn.close()
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    check_admin_user() 