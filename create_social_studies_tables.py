import psycopg2
from dotenv import load_dotenv
import os
import json

# 環境変数の読み込み
load_dotenv(dotenv_path='dbname.env')

# データベース接続情報
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')

def create_social_studies_tables():
    """社会科一問一答機能用のテーブルを作成"""
    
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
    -- 社会科問題テーブル
    CREATE TABLE IF NOT EXISTS social_studies_questions (
        id SERIAL PRIMARY KEY,
        subject VARCHAR(50) NOT NULL,
        question TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        acceptable_answers TEXT,  -- JSON形式で許容回答を保存
        explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- 社会科学習ログテーブル
    CREATE TABLE IF NOT EXISTS social_studies_study_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        user_answer TEXT NOT NULL,
        is_correct BOOLEAN NOT NULL,
        subject VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES social_studies_questions(id) ON DELETE CASCADE
    );
    
    -- インデックスの作成
    CREATE INDEX IF NOT EXISTS idx_social_studies_questions_subject ON social_studies_questions(subject);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_user_id ON social_studies_study_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_subject ON social_studies_study_log(subject);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_created_at ON social_studies_study_log(created_at);
    """
    
    try:
        # テーブルを作成
        cur.execute(create_tables_sql)
        conn.commit()
        print("✅ 社会科一問一答機能用テーブルが正常に作成されました。")
        
        # サンプル問題を追加
        sample_questions = [
            {
                'subject': '地理',
                'question': '日本の首都はどこですか？',
                'correct_answer': '東京',
                'acceptable_answers': json.dumps(['東京都', 'Tokyo']),
                'explanation': '日本の首都は東京です。'
            },
            {
                'subject': '地理',
                'question': '日本で最も高い山は何ですか？',
                'correct_answer': '富士山',
                'acceptable_answers': json.dumps(['富士', 'Mount Fuji']),
                'explanation': '日本で最も高い山は富士山（3,776m）です。'
            },
            {
                'subject': '歴史',
                'question': '江戸幕府を開いた人物は誰ですか？',
                'correct_answer': '徳川家康',
                'acceptable_answers': json.dumps(['徳川家康公', 'Tokugawa Ieyasu']),
                'explanation': '1603年に徳川家康が江戸幕府を開きました。'
            },
            {
                'subject': '歴史',
                'question': '明治維新が始まった年は何年ですか？',
                'correct_answer': '1868年',
                'acceptable_answers': json.dumps(['1868', '明治元年']),
                'explanation': '明治維新は1868年（明治元年）に始まりました。'
            },
            {
                'subject': '公民',
                'question': '日本の国会は何院制ですか？',
                'correct_answer': '二院制',
                'acceptable_answers': json.dumps(['2院制', '両院制']),
                'explanation': '日本の国会は衆議院と参議院の二院制です。'
            },
            {
                'subject': '公民',
                'question': '日本の憲法は何条から構成されていますか？',
                'correct_answer': '103条',
                'acceptable_answers': json.dumps(['103', '103条']),
                'explanation': '日本国憲法は103条から構成されています。'
            }
        ]
        
        for question_data in sample_questions:
            cur.execute('''
                INSERT INTO social_studies_questions (subject, question, correct_answer, acceptable_answers, explanation)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (
                question_data['subject'],
                question_data['question'],
                question_data['correct_answer'],
                question_data['acceptable_answers'],
                question_data['explanation']
            ))
        
        conn.commit()
        print("✅ サンプル問題を追加しました。")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        # 接続を閉じる
        cur.close()
        conn.close()

if __name__ == '__main__':
    create_social_studies_tables() 