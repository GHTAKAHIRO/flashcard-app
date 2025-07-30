import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def test_admin_login():
    """adminユーザーのログインをテスト"""
    db_path = 'flashcards.db'
    
    print("🔍 adminユーザーのログイン情報を確認中...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # adminユーザーを検索
        cursor.execute('SELECT id, username, password_hash, is_admin FROM users WHERE username = ?', ('admin',))
        admin_user = cursor.fetchone()
        
        if admin_user:
            user_id, username, password_hash, is_admin = admin_user
            print(f"✅ adminユーザーが見つかりました:")
            print(f"  ID: {user_id}")
            print(f"  Username: {username}")
            print(f"  Is Admin: {is_admin}")
            print(f"  Password Hash: {password_hash}")
            print(f"  Hash Length: {len(password_hash) if password_hash else 0}")
            
            # パスワードテスト
            test_passwords = ['admin', 'password', '123456', 'admin123']
            print("\n🔑 パスワードテスト:")
            
            for test_pwd in test_passwords:
                if password_hash and check_password_hash(password_hash, test_pwd):
                    print(f"  ✅ '{test_pwd}' が一致しました！")
                    break
            else:
                print("  ❌ テストパスワードでは一致しませんでした")
                
                # パスワードをリセット
                print("\n🔄 パスワードをリセットします...")
                new_password = 'admin'
                new_hash = generate_password_hash(new_password)
                
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
                conn.commit()
                
                print(f"✅ パスワードをリセットしました:")
                print(f"  新しいパスワード: {new_password}")
                print(f"  新しいハッシュ: {new_hash}")
        else:
            print("❌ adminユーザーが見つかりませんでした")
            
            # 全ユーザーを表示
            cursor.execute('SELECT id, username, is_admin FROM users ORDER BY id')
            users = cursor.fetchall()
            
            print("\n👥 登録されているユーザー:")
            for user in users:
                user_id, username, is_admin = user
                admin_status = "✅" if is_admin else "❌"
                print(f"  - ID: {user_id}, Username: {username}, Admin: {admin_status}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_admin_login() 