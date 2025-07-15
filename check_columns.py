import psycopg2
from dotenv import load_dotenv
import os

# 環境変数の読み込み
load_dotenv('dbname.env')

# データベースに接続
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database='dbname',
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)

cur = conn.cursor()

# テーブルのカラムを確認
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'social_studies_questions' ORDER BY ordinal_position;")
columns = [row[0] for row in cur.fetchall()]

print('social_studies_questionsテーブルのカラム:')
for column in columns:
    print(f'  - {column}')

conn.close() 