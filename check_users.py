import sqlite3
import os

def check_users():
    """データベースのユーザー情報を確認"""
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # ユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        print(f"📊 ユーザー数: {user_count}")
        
        # 最新のユーザーを表示
        cur.execute('''
            SELECT id, username, full_name, is_admin, created_at 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        users = cur.fetchall()
        if users:
            print("\n📋 最新のユーザー:")
            for user in users:
                print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日時: {user[4]}")
        else:
            print("❌ ユーザーが見つかりません")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    check_users() 