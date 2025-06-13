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

# テーブル作成のSQL
create_tables_sql = """
CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    source VARCHAR(255),
    page_number INTEGER,
    question TEXT,
    answer TEXT,
    difficulty VARCHAR(1),
    chunk_number INTEGER
);

CREATE TABLE IF NOT EXISTS chunk_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    source VARCHAR(255),
    stage INTEGER,
    page_range VARCHAR(255),
    difficulty VARCHAR(255),
    chunk_number INTEGER,
    test_completed BOOLEAN DEFAULT FALSE,
    practice_completed BOOLEAN DEFAULT FALSE
);
"""

try:
    # テーブルを作成
    cur.execute(create_tables_sql)
    conn.commit()
    print("テーブルが正常に作成されました。")
except Exception as e:
    print(f"エラーが発生しました: {e}")
    conn.rollback()
finally:
    # 接続を閉じる
    cur.close()
    conn.close() 