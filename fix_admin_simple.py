import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

print("🔧 管理者パスワード修正開始")

try:
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    # Check admin user
    cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if admin:
        user_id, username, current_hash = admin
        print(f"管理者ユーザー: ID={user_id}, ユーザー名={username}")
        print(f"現在のハッシュ: {current_hash[:50]}...")
        
        # Generate new password hash
        new_password = 'admin'
        new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        print(f"新しいパスワード: {new_password}")
        print(f"新しいハッシュ: {new_hash[:50]}...")
        
        # Update password
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))
        conn.commit()
        
        # Verify password
        if check_password_hash(new_hash, new_password):
            print("✅ パスワード更新成功")
            print("✅ パスワード検証成功")
        else:
            print("❌ パスワード検証失敗")
        
        print("管理者ログイン情報:")
        print("ユーザー名: admin")
        print("パスワード: admin")
    else:
        print("❌ 管理者ユーザーが見つかりません")
    
    conn.close()
    
except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    print(f"詳細エラー: {traceback.format_exc()}") 