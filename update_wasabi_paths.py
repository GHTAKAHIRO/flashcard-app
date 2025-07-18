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

# 現在のWasabiフォルダパスを確認
cur.execute("SELECT id, name, wasabi_folder_path FROM social_studies_textbooks;")
textbooks = cur.fetchall()

print('現在のWasabiフォルダパス:')
for textbook in textbooks:
    print(f'  ID: {textbook[0]}, 名前: {textbook[1]}, フォルダパス: {textbook[2]}')

# Wasabiフォルダパスを更新
update_mapping = {
    '社会/ファイナルステージ/地理': 'geography/final',
    '社会/ファイナルステージ/歴史': 'history/final',
    '社会/ファイナルステージ/公民': 'civics/final'
}

for old_path, new_path in update_mapping.items():
    cur.execute("UPDATE social_studies_textbooks SET wasabi_folder_path = %s WHERE wasabi_folder_path = %s", (new_path, old_path))
    print(f'更新: {old_path} → {new_path}')

conn.commit()

# 更新後の確認
cur.execute("SELECT id, name, wasabi_folder_path FROM social_studies_textbooks;")
textbooks = cur.fetchall()

print('\n更新後のWasabiフォルダパス:')
for textbook in textbooks:
    print(f'  ID: {textbook[0]}, 名前: {textbook[1]}, フォルダパス: {textbook[2]}')

conn.close() 