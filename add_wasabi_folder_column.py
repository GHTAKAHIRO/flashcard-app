import psycopg2
from dotenv import load_dotenv
import os

# 環境変数の読み込み
load_dotenv(dotenv_path='dbname.env')

# データベース接続情報
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')

def add_wasabi_folder_column():
    """教材テーブルにWasabiフォルダパスカラムを追加"""
    
    # データベースに接続
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    
    # カーソルを作成
    cur = conn.cursor()
    
    try:
        # wasabi_folder_pathカラムを追加
        cur.execute("""
            ALTER TABLE social_studies_textbooks 
            ADD COLUMN IF NOT EXISTS wasabi_folder_path VARCHAR(255) DEFAULT 'question_images'
        """)
        
        conn.commit()
        print("✅ 教材テーブルにwasabi_folder_pathカラムを追加しました。")
        
        # 既存の教材にデフォルトフォルダパスを設定
        cur.execute("""
            UPDATE social_studies_textbooks 
            SET wasabi_folder_path = 'question_images' 
            WHERE wasabi_folder_path IS NULL
        """)
        
        conn.commit()
        print("✅ 既存の教材にデフォルトフォルダパスを設定しました。")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_wasabi_folder_column() 