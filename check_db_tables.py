import sqlite3
import os

def check_database():
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"データベースファイル {db_path} が見つかりません")
        return
    
    print(f"データベースファイル: {db_path}")
    print(f"ファイルサイズ: {os.path.getsize(db_path)} bytes")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\nテーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 社会科関連のテーブルの内容を確認
        social_tables = ['social_studies_textbooks', 'social_studies_units', 'social_studies_questions']
        
        for table_name in social_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"\n{table_name}: {count} 件")
                
                if count > 0:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                    rows = cursor.fetchall()
                    print("  最新の3件:")
                    for row in rows:
                        print(f"    {row}")
                        
            except sqlite3.OperationalError as e:
                print(f"  {table_name}: テーブルが存在しません - {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"データベース接続エラー: {e}")

if __name__ == "__main__":
    check_database() 