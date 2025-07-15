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
    -- 教材テーブル
    CREATE TABLE IF NOT EXISTS social_studies_textbooks (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        subject VARCHAR(50) NOT NULL,
        grade VARCHAR(20),
        publisher VARCHAR(100),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- 単元テーブル
    CREATE TABLE IF NOT EXISTS social_studies_units (
        id SERIAL PRIMARY KEY,
        textbook_id INTEGER NOT NULL,
        name VARCHAR(200) NOT NULL,
        chapter_number INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (textbook_id) REFERENCES social_studies_textbooks(id) ON DELETE CASCADE
    );
    
    -- 社会科問題テーブル（拡張版）
    CREATE TABLE IF NOT EXISTS social_studies_questions (
        id SERIAL PRIMARY KEY,
        subject VARCHAR(50) NOT NULL,
        textbook_id INTEGER,
        unit_id INTEGER,
        question TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        acceptable_answers TEXT,  -- JSON形式で許容回答を保存
        explanation TEXT,
        image_url TEXT,  -- 問題に関連する画像のURL
        difficulty_level VARCHAR(20) DEFAULT 'basic', -- basic, intermediate, advanced
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (textbook_id) REFERENCES social_studies_textbooks(id) ON DELETE SET NULL,
        FOREIGN KEY (unit_id) REFERENCES social_studies_units(id) ON DELETE SET NULL
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
    CREATE INDEX IF NOT EXISTS idx_social_studies_textbooks_subject ON social_studies_textbooks(subject);
    CREATE INDEX IF NOT EXISTS idx_social_studies_units_textbook_id ON social_studies_units(textbook_id);
    CREATE INDEX IF NOT EXISTS idx_social_studies_questions_subject ON social_studies_questions(subject);
    CREATE INDEX IF NOT EXISTS idx_social_studies_questions_textbook_id ON social_studies_questions(textbook_id);
    CREATE INDEX IF NOT EXISTS idx_social_studies_questions_unit_id ON social_studies_questions(unit_id);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_user_id ON social_studies_study_log(user_id);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_subject ON social_studies_study_log(subject);
    CREATE INDEX IF NOT EXISTS idx_social_studies_study_log_created_at ON social_studies_study_log(created_at);
    """
    
    try:
        # テーブルを作成
        cur.execute(create_tables_sql)
        conn.commit()
        print("✅ 社会科一問一答機能用テーブルが正常に作成されました。")
        
        # サンプル教材を追加
        sample_textbooks = [
            {
                'name': '中学社会 地理的分野',
                'subject': '地理',
                'grade': '中学1年',
                'publisher': '東京書籍',
                'description': '中学校地理的分野の標準的な教科書'
            },
            {
                'name': '中学社会 歴史的分野',
                'subject': '歴史',
                'grade': '中学2年',
                'publisher': '東京書籍',
                'description': '中学校歴史的分野の標準的な教科書'
            },
            {
                'name': '中学社会 公民的分野',
                'subject': '公民',
                'grade': '中学3年',
                'publisher': '東京書籍',
                'description': '中学校公民的分野の標準的な教科書'
            }
        ]
        
        for textbook_data in sample_textbooks:
            cur.execute('''
                INSERT INTO social_studies_textbooks (name, subject, grade, publisher, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (
                textbook_data['name'],
                textbook_data['subject'],
                textbook_data['grade'],
                textbook_data['publisher'],
                textbook_data['description']
            ))
        
        conn.commit()
        print("✅ サンプル教材を追加しました。")
        
        # サンプル単元を追加
        sample_units = [
            {
                'textbook_id': 1,  # 地理
                'name': '世界の地域構成',
                'chapter_number': 1,
                'description': '世界の地域区分と特色について学習します'
            },
            {
                'textbook_id': 1,  # 地理
                'name': '世界の諸地域',
                'chapter_number': 2,
                'description': '世界の主要な地域の特色について学習します'
            },
            {
                'textbook_id': 2,  # 歴史
                'name': '古代までの日本',
                'chapter_number': 1,
                'description': '古代までの日本の歴史について学習します'
            },
            {
                'textbook_id': 2,  # 歴史
                'name': '中世の日本',
                'chapter_number': 2,
                'description': '中世の日本の歴史について学習します'
            },
            {
                'textbook_id': 3,  # 公民
                'name': '現代社会と私たち',
                'chapter_number': 1,
                'description': '現代社会の特色と私たちの生活について学習します'
            },
            {
                'textbook_id': 3,  # 公民
                'name': '私たちと政治',
                'chapter_number': 2,
                'description': '日本の政治制度について学習します'
            }
        ]
        
        for unit_data in sample_units:
            cur.execute('''
                INSERT INTO social_studies_units (textbook_id, name, chapter_number, description)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (
                unit_data['textbook_id'],
                unit_data['name'],
                unit_data['chapter_number'],
                unit_data['description']
            ))
        
        conn.commit()
        print("✅ サンプル単元を追加しました。")
        
        # サンプル問題を追加（教材・単元と関連付け）
        sample_questions = [
            {
                'subject': '地理',
                'textbook_id': 1,
                'unit_id': 1,
                'question': '日本の首都はどこですか？',
                'correct_answer': '東京',
                'acceptable_answers': json.dumps(['東京都', 'Tokyo']),
                'explanation': '日本の首都は東京です。',
                'difficulty_level': 'basic'
            },
            {
                'subject': '地理',
                'textbook_id': 1,
                'unit_id': 1,
                'question': '日本で最も高い山は何ですか？',
                'correct_answer': '富士山',
                'acceptable_answers': json.dumps(['富士', 'Mount Fuji']),
                'explanation': '日本で最も高い山は富士山（3,776m）です。',
                'difficulty_level': 'basic'
            },
            {
                'subject': '歴史',
                'textbook_id': 2,
                'unit_id': 3,
                'question': '江戸幕府を開いた人物は誰ですか？',
                'correct_answer': '徳川家康',
                'acceptable_answers': json.dumps(['徳川家康公', 'Tokugawa Ieyasu']),
                'explanation': '1603年に徳川家康が江戸幕府を開きました。',
                'difficulty_level': 'intermediate'
            },
            {
                'subject': '歴史',
                'textbook_id': 2,
                'unit_id': 4,
                'question': '明治維新が始まった年は何年ですか？',
                'correct_answer': '1868年',
                'acceptable_answers': json.dumps(['1868', '明治元年']),
                'explanation': '明治維新は1868年（明治元年）に始まりました。',
                'difficulty_level': 'intermediate'
            },
            {
                'subject': '公民',
                'textbook_id': 3,
                'unit_id': 5,
                'question': '日本の国会は何院制ですか？',
                'correct_answer': '二院制',
                'acceptable_answers': json.dumps(['2院制', '両院制']),
                'explanation': '日本の国会は衆議院と参議院の二院制です。',
                'difficulty_level': 'basic'
            },
            {
                'subject': '公民',
                'textbook_id': 3,
                'unit_id': 6,
                'question': '日本の憲法は何条から構成されていますか？',
                'correct_answer': '103条',
                'acceptable_answers': json.dumps(['103', '103条']),
                'explanation': '日本国憲法は103条から構成されています。',
                'difficulty_level': 'advanced'
            }
        ]
        
        for question_data in sample_questions:
            cur.execute('''
                INSERT INTO social_studies_questions (subject, textbook_id, unit_id, question, correct_answer, acceptable_answers, explanation, difficulty_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', (
                question_data['subject'],
                question_data['textbook_id'],
                question_data['unit_id'],
                question_data['question'],
                question_data['correct_answer'],
                question_data['acceptable_answers'],
                question_data['explanation'],
                question_data['difficulty_level']
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