#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv(dotenv_path='dbname.env')

def create_vocabulary_tables():
    """英単語システム用のテーブルを作成"""
    
    # データベース接続情報
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    
    try:
        # データベースに接続
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        with conn.cursor() as cur:
            print("🔧 英単語システム用テーブルを作成中...")
            
            # 英単語テーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS vocabulary_words (
                    id SERIAL PRIMARY KEY,
                    word VARCHAR(255) NOT NULL,
                    meaning TEXT NOT NULL,
                    example_sentence TEXT,
                    source VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(word, source)
                )
            ''')
            print("✅ vocabulary_words テーブルを作成しました")
            
            # 英単語学習ログテーブル
            cur.execute('''
                CREATE TABLE IF NOT EXISTS vocabulary_study_log (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    word_id INTEGER NOT NULL,
                    result VARCHAR(20) NOT NULL CHECK (result IN ('known', 'unknown')),
                    source VARCHAR(100) NOT NULL,
                    study_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (word_id) REFERENCES vocabulary_words(id) ON DELETE CASCADE
                )
            ''')
            print("✅ vocabulary_study_log テーブルを作成しました")
            
            # インデックスを作成
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_vocabulary_words_source 
                ON vocabulary_words(source)
            ''')
            
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_vocabulary_study_log_user_date 
                ON vocabulary_study_log(user_id, study_date DESC)
            ''')
            
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_vocabulary_study_log_word_result 
                ON vocabulary_study_log(word_id, result)
            ''')
            
            print("✅ インデックスを作成しました")
            
            # サンプルデータを挿入
            sample_words = [
                # 基本英単語
                ('hello', 'こんにちは', 'Hello, how are you?', 'basic'),
                ('world', '世界', 'The world is beautiful.', 'basic'),
                ('study', '勉強する', 'I study English every day.', 'basic'),
                ('work', '働く', 'I work at a company.', 'basic'),
                ('home', '家', 'Welcome to my home.', 'basic'),
                ('friend', '友達', 'She is my best friend.', 'basic'),
                ('family', '家族', 'I love my family.', 'basic'),
                ('school', '学校', 'I go to school by bus.', 'basic'),
                ('book', '本', 'I read a book every night.', 'basic'),
                ('time', '時間', 'What time is it?', 'basic'),
                
                # TOEIC単語
                ('business', 'ビジネス', 'Business is booming.', 'toeic'),
                ('meeting', '会議', 'We have a meeting at 3 PM.', 'toeic'),
                ('project', 'プロジェクト', 'This project is very important.', 'toeic'),
                ('client', 'クライアント', 'Our client is satisfied.', 'toeic'),
                ('budget', '予算', 'We need to stay within budget.', 'toeic'),
                ('deadline', '締切', 'The deadline is next Friday.', 'toeic'),
                ('schedule', 'スケジュール', 'Please check your schedule.', 'toeic'),
                ('presentation', 'プレゼンテーション', 'I will give a presentation tomorrow.', 'toeic'),
                ('negotiation', '交渉', 'The negotiation was successful.', 'toeic'),
                ('contract', '契約', 'We signed the contract yesterday.', 'toeic'),
                
                # 大学受験単語
                ('academic', '学術的な', 'This is an academic paper.', 'university'),
                ('research', '研究', 'He is doing research on cancer.', 'university'),
                ('analysis', '分析', 'The analysis shows interesting results.', 'university'),
                ('theory', '理論', 'Einstein\'s theory of relativity.', 'university'),
                ('hypothesis', '仮説', 'We need to test this hypothesis.', 'university'),
                ('experiment', '実験', 'The experiment was successful.', 'university'),
                ('conclusion', '結論', 'What is your conclusion?', 'university'),
                ('evidence', '証拠', 'There is no evidence to support this.', 'university'),
                ('argument', '議論', 'This is a strong argument.', 'university'),
                ('debate', '討論', 'The debate was very heated.', 'university')
            ]
            
            for word, meaning, example, source in sample_words:
                try:
                    cur.execute('''
                        INSERT INTO vocabulary_words (word, meaning, example_sentence, source)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (word, source) DO NOTHING
                    ''', (word, meaning, example, source))
                except Exception as e:
                    print(f"⚠️ サンプルデータ挿入エラー: {word} - {e}")
            
            conn.commit()
            print("✅ サンプルデータを挿入しました")
            
            # 統計を表示
            cur.execute('''
                SELECT source, COUNT(*) as count 
                FROM vocabulary_words 
                GROUP BY source 
                ORDER BY source
            ''')
            
            print("\n📊 登録済み単語数:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}語")
            
        conn.close()
        print("\n🎉 英単語システムのテーブル作成が完了しました！")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return False
    
    return True

if __name__ == '__main__':
    create_vocabulary_tables() 