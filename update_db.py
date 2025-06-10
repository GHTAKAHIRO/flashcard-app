import sqlite3

def update_database():
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    try:
        # 新しいカラムを追加
        cursor.execute('ALTER TABLE users ADD COLUMN full_name TEXT')
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        
        # 既存のユーザーを管理者として設定（最初のユーザーのみ）
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = 1')
        
        conn.commit()
        print("データベースの更新が完了しました")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    update_database() 