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

def add_image_url_column():
    """social_studies_questionsテーブルにimage_urlカラムを追加"""
    
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
        # image_urlカラムが存在するかチェック
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'social_studies_questions' 
            AND column_name = 'image_url'
        """)
        
        if cur.fetchone():
            print("✅ image_urlカラムは既に存在します。")
        else:
            # image_urlカラムを追加
            cur.execute("""
                ALTER TABLE social_studies_questions 
                ADD COLUMN image_url TEXT
            """)
            conn.commit()
            print("✅ image_urlカラムを追加しました。")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_image_url_column() 