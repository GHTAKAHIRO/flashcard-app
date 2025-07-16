#!/usr/bin/env python3
"""
Wasabiフォルダパス管理用カラムを追加するスクリプト
"""

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

def add_wasabi_folder_path_columns():
    """教材と単元テーブルにWasabiフォルダパス管理用のカラムを追加"""
    
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
        # 教材テーブルにwasabi_folder_pathカラムを追加
        cur.execute("""
            ALTER TABLE social_studies_textbooks 
            ADD COLUMN IF NOT EXISTS wasabi_folder_path VARCHAR(200)
        """)
        
        # 単元テーブルにwasabi_folder_pathカラムを追加
        cur.execute("""
            ALTER TABLE social_studies_units 
            ADD COLUMN IF NOT EXISTS wasabi_folder_path VARCHAR(200)
        """)
        
        # 問題テーブルにwasabi_folder_pathカラムを追加（問題レベルでの指定も可能）
        cur.execute("""
            ALTER TABLE social_studies_questions 
            ADD COLUMN IF NOT EXISTS wasabi_folder_path VARCHAR(200)
        """)
        
        conn.commit()
        print("✅ Wasabiフォルダパス管理用カラムを追加しました。")
        
        # 既存データのサンプル更新
        print("🔍 既存データのサンプル更新...")
        
        # 教材のサンプル更新
        sample_updates = [
            (1, "社会/ファイナルステージ/地理"),  # 地理教材
            (2, "社会/ファイナルステージ/歴史"),  # 歴史教材
            (3, "社会/ファイナルステージ/公民"),  # 公民教材
        ]
        
        for textbook_id, folder_path in sample_updates:
            cur.execute("""
                UPDATE social_studies_textbooks 
                SET wasabi_folder_path = %s 
                WHERE id = %s
            """, (folder_path, textbook_id))
        
        conn.commit()
        print("✅ サンプル教材のWasabiフォルダパスを更新しました。")
        
        # 現在の設定を確認
        cur.execute("""
            SELECT id, name, subject, wasabi_folder_path 
            FROM social_studies_textbooks 
            ORDER BY id
        """)
        
        textbooks = cur.fetchall()
        print("\n📋 現在の教材設定:")
        for textbook in textbooks:
            print(f"  ID: {textbook[0]}, 名前: {textbook[1]}, 教科: {textbook[2]}, フォルダ: {textbook[3] or '未設定'}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    add_wasabi_folder_path_columns() 