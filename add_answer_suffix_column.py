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

def add_answer_suffix_column():
    """social_studies_questionsテーブルにanswer_suffixカラムを追加"""
    
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
        # answer_suffixカラムが存在するかチェック
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'social_studies_questions' 
            AND column_name = 'answer_suffix'
        """)
        
        if cur.fetchone():
            print("✅ answer_suffixカラムは既に存在します。")
        else:
            # answer_suffixカラムを追加
            cur.execute("""
                ALTER TABLE social_studies_questions 
                ADD COLUMN answer_suffix VARCHAR(100)
            """)
            conn.commit()
            print("✅ answer_suffixカラムを追加しました。")
        
        # テーブル構造を確認
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'social_studies_questions'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        print("\n📋 social_studies_questionsテーブルの構造:")
        for column in columns:
            print(f"  - {column[0]}: {column[1]} ({'NULL可' if column[2] == 'YES' else 'NOT NULL'})")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_answer_suffix_column() 