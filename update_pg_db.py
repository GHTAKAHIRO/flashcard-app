import psycopg2
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

def update_database():
    # 環境変数の読み込み
    load_dotenv('dbname.env')
    
    # データベース接続情報
    conn_params = {
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT'),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD')
    }
    
    try:
        # データベースに接続
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # テーブルの存在確認
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        
        if not cursor.fetchone()[0]:
            # usersテーブルが存在しない場合は作成
            cursor.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    last_login TIMESTAMP
                );
            """)
            conn.commit()
        else:
            # 既存のテーブルにカラムを追加（各カラムを個別のトランザクションで実行）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(255);")
                conn.commit()
            except psycopg2.Error as e:
                if "already exists" not in str(e):
                    raise
                print("full_nameカラムは既に存在します")
                conn.rollback()
            
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;")
                conn.commit()
            except psycopg2.Error as e:
                if "already exists" not in str(e):
                    raise
                print("is_adminカラムは既に存在します")
                conn.rollback()
            
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP;")
                conn.commit()
            except psycopg2.Error as e:
                if "already exists" not in str(e):
                    raise
                print("last_loginカラムは既に存在します")
                conn.rollback()
        
        # study_logテーブルの作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                source VARCHAR(255),
                stage INTEGER,
                card_id INTEGER,
                result VARCHAR(50),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        
        # system_settingsテーブルの作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL PRIMARY KEY,
                chunk_size INTEGER DEFAULT 10,
                session_timeout INTEGER DEFAULT 120,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        
        # デフォルト設定の挿入（テーブルが空の場合のみ）
        cursor.execute("""
            INSERT INTO system_settings (chunk_size, session_timeout)
            SELECT 10, 120
            WHERE NOT EXISTS (SELECT 1 FROM system_settings);
        """)
        conn.commit()
        
        # 管理者ユーザーの作成
        password_hash = generate_password_hash('admin123')
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, is_admin)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (username) 
            DO UPDATE SET 
                password_hash = EXCLUDED.password_hash,
                full_name = EXCLUDED.full_name,
                is_admin = EXCLUDED.is_admin;
        """, ('admin', password_hash, '管理者', True))
        
        conn.commit()
        print("データベースの更新が完了しました")
        print("管理者ユーザーの情報:")
        print("ユーザー名: admin")
        print("パスワード: admin123")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    update_database() 