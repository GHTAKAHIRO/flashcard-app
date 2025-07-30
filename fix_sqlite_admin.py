import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_admin_user():
    """SQLiteデータベースにadminユーザーを作成"""
    db_path = 'flashcards.db'
    
    print(f"📁 データベースパス: {db_path}")
    print(f"📁 ファイル存在: {os.path.exists(db_path)}")
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("✅ SQLiteデータベースに接続しました")
        
        # テーブル一覧を確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("📋 テーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        
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
        
        # 全ユーザーを表示
        cursor.execute('SELECT id, username, is_admin, full_name FROM users ORDER BY id')
        users = cursor.fetchall()
        
        print("\n👥 ユーザー一覧:")
        print("ID | ユーザー名 | 管理者権限 | 表示名")
        print("-" * 50)
        
        for user in users:
            user_id, username, is_admin, full_name = user
            admin_status = "✅" if is_admin else "❌"
            print(f"{user_id:2d} | {username:10s} | {admin_status:8s} | {full_name or '':10s}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_admin_user() 