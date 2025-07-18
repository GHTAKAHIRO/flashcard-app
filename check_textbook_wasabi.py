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

# 教材テーブルのWasabiフォルダパスを確認
cur.execute("SELECT id, name, wasabi_folder_path FROM social_studies_textbooks;")
textbooks = cur.fetchall()

print('教材テーブルのWasabiフォルダパス:')
for textbook in textbooks:
    print(f'  ID: {textbook[0]}, 名前: {textbook[1]}, フォルダパス: {textbook[2]}')

conn.close() 