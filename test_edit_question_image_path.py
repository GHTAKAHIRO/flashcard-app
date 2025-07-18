#!/usr/bin/env python3
"""
問題編集画面の画像パス表示機能テストスクリプト
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

def test_edit_question_image_path():
    """問題編集画面の画像パス表示機能テスト"""
    
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
        print("🔍 問題編集画面の画像パス表示機能テスト開始")
        
        # 1. 問題ID 16の情報を取得
        print("\n1. 問題ID 16の情報を取得")
        cur.execute('''
            SELECT q.id, q.subject, q.textbook_id, q.unit_id, q.question, q.correct_answer, 
                   q.acceptable_answers, q.answer_suffix, q.explanation, q.difficulty_level,
                   q.image_name, q.image_url, t.name as textbook_name, u.name as unit_name,
                   t.subject as textbook_subject, u.chapter_number, t.wasabi_folder_path
            FROM social_studies_questions q
            LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
            LEFT JOIN social_studies_units u ON q.unit_id = u.id
            WHERE q.id = 16
        ''')
        
        question = cur.fetchone()
        if not question:
            print("❌ 問題ID 16が見つかりません")
            return
        
        print("✅ 問題情報:")
        print(f"  問題ID: {question[0]}")
        print(f"  科目: {question[1]}")
        print(f"  教材ID: {question[2]}")
        print(f"  単元ID: {question[3]}")
        print(f"  問題文: {question[4][:50]}...")
        print(f"  正解: {question[5]}")
        print(f"  教材名: {question[12]}")
        print(f"  単元名: {question[13]}")
        print(f"  教材科目: {question[14]}")
        print(f"  章番号: {question[15]}")
        print(f"  Wasabiフォルダパス: {question[16]}")
        print(f"  画像名: {question[10]}")
        print(f"  画像URL: {question[11]}")
        
        # 2. 教材情報を取得
        print("\n2. 教材情報を取得")
        if question[2]:  # textbook_id
            cur.execute('SELECT * FROM social_studies_textbooks WHERE id = %s', (question[2],))
            textbook_info = cur.fetchone()
            if textbook_info:
                print("✅ 教材情報:")
                print(f"  教材ID: {textbook_info[0]}")
                print(f"  教材名: {textbook_info[1]}")
                print(f"  科目: {textbook_info[2]}")
                print(f"  Wasabiフォルダパス: {textbook_info[6] if len(textbook_info) > 6 else 'N/A'}")
            else:
                print("❌ 教材情報が見つかりません")
        else:
            print("⚠️ 教材IDが設定されていません")
        
        # 3. 単元情報を取得
        print("\n3. 単元情報を取得")
        if question[3]:  # unit_id
            cur.execute('SELECT * FROM social_studies_units WHERE id = %s', (question[3],))
            unit_info = cur.fetchone()
            if unit_info:
                print("✅ 単元情報:")
                print(f"  単元ID: {unit_info[0]}")
                print(f"  教材ID: {unit_info[1]}")
                print(f"  単元名: {unit_info[2]}")
                print(f"  章番号: {unit_info[3]}")
            else:
                print("❌ 単元情報が見つかりません")
        else:
            print("⚠️ 単元IDが設定されていません")
        
        # 4. 画像パス情報を生成（バックエンドと同じロジック）
        print("\n4. 画像パス情報を生成")
        if question[2] and question[3]:  # textbook_id と unit_id が両方存在
            chapter_number = question[15] or 1  # chapter_number
            wasabi_folder_path = question[16]  # wasabi_folder_path
            
            if wasabi_folder_path:
                base_image_url = f"https://s3.ap-northeast-1-ntt.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{wasabi_folder_path}/{chapter_number}"
                print("✅ 生成された画像パス情報:")
                print(f"  章番号: {chapter_number}")
                print(f"  Wasabiフォルダパス: {wasabi_folder_path}")
                print(f"  ベース画像URL: {base_image_url}")
                
                # この単元に画像が設定されている問題数を取得
                cur.execute('''
                    SELECT COUNT(*) as count
                    FROM social_studies_questions
                    WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
                ''', (question[2], question[3]))
                image_questions_count = cur.fetchone()[0]
                print(f"  画像が設定されている問題数: {image_questions_count}件")
                
                # 画像パス情報オブジェクト
                image_path_info = {
                    'base_url': base_image_url,
                    'chapter_number': chapter_number,
                    'wasabi_folder_path': wasabi_folder_path,
                    'image_questions_count': image_questions_count
                }
                print("✅ 画像パス情報オブジェクト:")
                print(f"  {image_path_info}")
            else:
                print("❌ Wasabiフォルダパスが設定されていません")
        else:
            print("❌ 教材IDまたは単元IDが不足しています")
        
        # 5. 現在の画像URLとの比較
        print("\n5. 現在の画像URLとの比較")
        current_image_url = question[11]  # image_url
        if current_image_url:
            print(f"現在の画像URL: {current_image_url}")
            
            if question[2] and question[3] and wasabi_folder_path:
                expected_base_url = f"https://s3.ap-northeast-1-ntt.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{wasabi_folder_path}/{chapter_number}"
                print(f"期待されるベースURL: {expected_base_url}")
                
                if current_image_url.startswith(expected_base_url):
                    print("✅ 画像URLは期待されるパスと一致しています")
                else:
                    print("⚠️ 画像URLが期待されるパスと一致していません")
                    print("   この問題の画像パスを更新する必要があります")
        else:
            print("⚠️ この問題には画像URLが設定されていません")
        
        # 6. 問題編集画面で表示されるべき情報
        print("\n6. 問題編集画面で表示されるべき情報")
        if question[2] and question[3] and wasabi_folder_path:
            print("✅ 問題編集画面で表示される画像データパス:")
            print(f"  {base_image_url}")
            print("✅ 画像名欄のプレースホルダー:")
            print("  例: 2（問題番号のみ）")
            print("✅ パス情報の説明:")
            print(f"  問題番号のみ入力してください（例: 2 → {base_image_url}/2.jpg）")
        else:
            print("❌ 画像パス情報を生成できません")
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    test_edit_question_image_path() 