import sqlite3
from werkzeug.security import generate_password_hash

def reset_admin_password():
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    try:
        # 管理者ユーザーのパスワードを更新
        password_hash = generate_password_hash('admin123')
        cursor.execute('''
            UPDATE users 
            SET password_hash = ?, is_admin = 1 
            WHERE username = 'admin'
        ''', (password_hash,))
        
        # 管理者ユーザーが存在しない場合は作成
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, is_admin)
                VALUES ('admin', ?, '管理者', 1)
            ''', (password_hash,))
        
        conn.commit()
        print("管理者ユーザーのパスワードをリセットしました")
        print("ユーザー名: admin")
        print("パスワード: admin123")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    reset_admin_password() 