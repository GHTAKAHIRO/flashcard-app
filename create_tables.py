import psycopg2
from dotenv import load_dotenv
import os
import json

# 環境変数の読み込み
load_dotenv()

# データベース接続情報
DB_NAME = os.getenv('DB_NAME', 'social_studies_quiz')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def create_tables():
    """データベーステーブルを作成"""
    
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
    -- ユーザーテーブル
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(100) NOT NULL,
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- 問題テーブル
    CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY,
        subject VARCHAR(50) NOT NULL,
        question TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        acceptable_answers TEXT,  -- JSON形式で許容回答を保存
        explanation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- 学習ログテーブル
    CREATE TABLE IF NOT EXISTS study_log (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        user_answer TEXT NOT NULL,
        is_correct BOOLEAN NOT NULL,
        subject VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
    );
    
    -- インデックスの作成
    CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);
    CREATE INDEX IF NOT EXISTS idx_study_log_user_id ON study_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_study_log_subject ON study_log(subject);
    CREATE INDEX IF NOT EXISTS idx_study_log_created_at ON study_log(created_at);
    """
    
    try:
        # テーブルを作成
        cur.execute(create_tables_sql)
        conn.commit()
        print("✅ テーブルが正常に作成されました。")
        
        # 管理者ユーザーを作成
        admin_username = "admin"
        admin_password = "admin123"
        admin_full_name = "管理者"
        
        # 管理者ユーザーが存在するかチェック
        cur.execute('SELECT id FROM users WHERE username = %s', (admin_username,))
        if not cur.fetchone():
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash(admin_password)
            cur.execute('''
                INSERT INTO users (username, password_hash, full_name, is_admin)
                VALUES (%s, %s, %s, %s)
            ''', (admin_username, password_hash, admin_full_name, True))
            conn.commit()
            print(f"✅ 管理者ユーザーを作成しました: {admin_username} / {admin_password}")
        else:
            print("✅ 管理者ユーザーは既に存在します")
        
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
                INSERT INTO questions (subject, question, correct_answer, acceptable_answers, explanation)
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
    create_tables() 