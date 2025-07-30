#!/usr/bin/env python3
"""
初期データ復元スクリプト
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

def restore_initial_data():
    """初期データを復元"""
    db_path = os.getenv('DB_PATH', 'flashcards.db')
    
    print(f"📁 データベースパス: {db_path}")
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 既存のユーザー数を確認
        cursor.execute('SELECT COUNT(*) FROM users')
        existing_user_count = cursor.fetchone()[0]
        print(f"👥 既存のユーザー数: {existing_user_count}")
        
        # 既存のユーザーがいる場合は警告
        if existing_user_count > 1:  # admin以外のユーザーがいる場合
            print("⚠️  警告: 既存のユーザーデータが存在します")
            print("   この操作は既存のユーザーデータに影響を与える可能性があります")
            
            # 既存のユーザー一覧を表示
            cursor.execute('SELECT id, username, is_admin, created_at FROM users ORDER BY created_at DESC')
            existing_users = cursor.fetchall()
            print("📊 既存のユーザー:")
            for user in existing_users:
                print(f"   ID: {user[0]}, ユーザー名: {user[1]}, 管理者: {user[2]}, 作成日: {user[3]}")
        
        # 管理者ユーザーの確認と作成
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            print("👤 管理者ユーザーを作成しています...")
            admin_password = generate_password_hash('admin')
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('admin', 'admin@example.com', admin_password, True, '管理者', datetime.now()))
            print("✅ 管理者ユーザーを作成しました")
        else:
            print("✅ 管理者ユーザーは既に存在します")
        
        # 入力問題教材の確認と作成
        cursor.execute('SELECT id FROM input_textbooks WHERE name = ?', ('ファイナルステージ',))
        if not cursor.fetchone():
            print("📚 初期教材を作成しています...")
            
            # 教材を作成
            cursor.execute('''
                INSERT INTO input_textbooks (name, subject, grade, publisher, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('ファイナルステージ', '地理', '高校', '出版社名', '地理の総合問題集', datetime.now()))
            
            textbook_id = cursor.lastrowid
            print(f"✅ 教材を作成しました: ID={textbook_id}")
            
            # 単元を作成
            units = [
                ('日本の自然環境', 1, '日本の地形・気候・自然災害について'),
                ('日本の産業', 2, '日本の農業・工業・サービス業について'),
                ('日本の人口・都市', 3, '日本の人口動態と都市問題について'),
                ('世界の自然環境', 4, '世界の地形・気候・自然環境について'),
                ('世界の産業・経済', 5, '世界の産業構造と経済について')
            ]
            
            for unit_name, chapter_num, description in units:
                cursor.execute('''
                    INSERT INTO input_units (textbook_id, name, chapter_number, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (textbook_id, unit_name, chapter_num, description, datetime.now()))
            
            print(f"✅ {len(units)}個の単元を作成しました")
            
            # サンプル問題を作成
            sample_questions = [
                ('日本の最高峰は？', '富士山', '日本一高い山は富士山です。', 'basic'),
                ('日本の首都は？', '東京', '日本の首都は東京です。', 'basic'),
                ('日本で最も人口が多い都道府県は？', '東京都', '東京都が最も人口が多いです。', 'normal'),
                ('日本の気候区分で最も多いのは？', '温帯', '日本は温帯気候が最も広く分布しています。', 'normal'),
                ('日本の主要な産業は？', '自動車産業', '自動車産業は日本の主要な産業の一つです。', 'advanced')
            ]
            
            for question, answer, explanation, difficulty in sample_questions:
                cursor.execute('''
                    INSERT INTO input_questions 
                    (subject, textbook_id, question, correct_answer, explanation, difficulty_level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', ('地理', textbook_id, question, answer, explanation, difficulty, datetime.now()))
            
            print(f"✅ {len(sample_questions)}個のサンプル問題を作成しました")
            
        else:
            print("✅ 初期教材は既に存在します")
        
        conn.commit()
        print("🎉 初期データの復元が完了しました")
        
        # 統計情報を表示
        cursor.execute('SELECT COUNT(*) FROM input_textbooks')
        textbook_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM input_units')
        unit_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM input_questions')
        question_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users')
        final_user_count = cursor.fetchone()[0]
        
        print(f"📊 現在のデータ統計:")
        print(f"   ユーザー数: {final_user_count}")
        print(f"   教材数: {textbook_count}")
        print(f"   単元数: {unit_count}")
        print(f"   問題数: {question_count}")
        
    except Exception as e:
        print(f"❌ データ復元エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    restore_initial_data() 