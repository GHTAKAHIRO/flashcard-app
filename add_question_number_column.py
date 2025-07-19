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

try:
    # question_numberカラムを追加
    cur.execute("ALTER TABLE social_studies_questions ADD COLUMN question_number INTEGER;")
    print("question_numberカラムを追加しました")
    
    # 既存の問題に連番を振る
    cur.execute("""
        UPDATE social_studies_questions 
        SET question_number = subquery.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY unit_id ORDER BY id) as row_num
            FROM social_studies_questions
        ) as subquery
        WHERE social_studies_questions.id = subquery.id
    """)
    print("既存の問題に連番を振りました")
    
    # コミット
    conn.commit()
    print("変更をコミットしました")
    
    # 確認
    cur.execute("SELECT unit_id, question_number, question FROM social_studies_questions ORDER BY unit_id, question_number LIMIT 10;")
    results = cur.fetchall()
    print("\n確認結果（最初の10件）:")
    for result in results:
        print(f"単元ID: {result[0]}, 問題番号: {result[1]}, 問題: {result[2][:50]}...")

except Exception as e:
    print(f"エラーが発生しました: {e}")
    conn.rollback()
finally:
    conn.close() 