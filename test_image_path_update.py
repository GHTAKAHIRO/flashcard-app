#!/usr/bin/env python3
"""
単元の画像パス一括更新機能のテストスクリプト
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

def test_image_path_update():
    """画像パス一括更新機能のテスト"""
    
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
        print("🔍 単元の画像パス一括更新機能テスト開始")
        
        # 1. テスト用の教材と単元を確認
        print("\n1. 既存の教材と単元を確認")
        cur.execute('''
            SELECT t.id, t.name, t.wasabi_folder_path, u.id, u.name, u.chapter_number
            FROM social_studies_textbooks t
            JOIN social_studies_units u ON t.id = u.textbook_id
            ORDER BY t.id, u.id
        ''')
        
        units = cur.fetchall()
        if not units:
            print("❌ テスト用の教材・単元が見つかりません")
            return
        
        print("✅ 見つかった単元:")
        for textbook_id, textbook_name, folder_path, unit_id, unit_name, chapter_number in units:
            print(f"  教材: {textbook_name} (ID: {textbook_id}, パス: {folder_path})")
            print(f"  単元: {unit_name} (ID: {unit_id}, 章: {chapter_number})")
        
        # 2. テスト用の単元を選択（最初の単元を使用）
        test_textbook_id, test_textbook_name, test_folder_path, test_unit_id, test_unit_name, test_chapter_number = units[0]
        
        print(f"\n2. テスト対象: 教材「{test_textbook_name}」の単元「{test_unit_name}」")
        
        # 3. 現在の問題と画像URLを確認
        print("\n3. 現在の問題と画像URLを確認")
        cur.execute('''
            SELECT id, question, image_url
            FROM social_studies_questions
            WHERE textbook_id = %s AND unit_id = %s
            ORDER BY id
        ''', (test_textbook_id, test_unit_id))
        
        questions = cur.fetchall()
        if not questions:
            print("❌ この単元には問題が登録されていません")
            return
        
        print(f"✅ 見つかった問題数: {len(questions)}件")
        for question_id, question_text, image_url in questions:
            print(f"  問題ID: {question_id}")
            print(f"  問題文: {question_text[:50]}...")
            print(f"  画像URL: {image_url or 'なし'}")
        
        # 4. 画像が設定されている問題数を確認
        cur.execute('''
            SELECT COUNT(*) as count
            FROM social_studies_questions
            WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
        ''', (test_textbook_id, test_unit_id))
        
        image_questions_count = cur.fetchone()[0]
        print(f"\n4. 画像が設定されている問題数: {image_questions_count}件")
        
        if image_questions_count == 0:
            print("⚠️ この単元には画像が設定されている問題がないため、テスト用の画像URLを設定します")
            
            # テスト用の画像URLを設定
            test_image_url = "https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/test/old/path/1.jpg"
            cur.execute('''
                UPDATE social_studies_questions
                SET image_url = %s
                WHERE textbook_id = %s AND unit_id = %s
                LIMIT 1
            ''', (test_image_url, test_textbook_id, test_unit_id))
            conn.commit()
            print(f"✅ テスト用画像URLを設定: {test_image_url}")
        
        # 5. 画像パス更新のシミュレーション
        print("\n5. 画像パス更新のシミュレーション")
        
        # 新しい画像URL
        new_image_url = "https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/test/new/path"
        
        # URLからパスを抽出
        url_parts = new_image_url.split('/')
        if len(url_parts) >= 6:
            bucket_index = url_parts.index('so-image') if 'so-image' in url_parts else -1
            if bucket_index != -1 and bucket_index + 1 < len(url_parts):
                folder_path = '/'.join(url_parts[bucket_index + 1:])
                path_parts = folder_path.split('/')
                if len(path_parts) > 1:
                    wasabi_folder_path = '/'.join(path_parts[:-1])
                else:
                    wasabi_folder_path = folder_path
            else:
                wasabi_folder_path = ''
        else:
            wasabi_folder_path = ''
        
        print(f"新しい画像URL: {new_image_url}")
        print(f"抽出されたパス: {wasabi_folder_path}")
        
        # 6. 問題の画像URL更新のシミュレーション
        print("\n6. 問題の画像URL更新のシミュレーション")
        
        cur.execute('''
            SELECT id, image_url FROM social_studies_questions
            WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
        ''', (test_textbook_id, test_unit_id))
        
        questions_to_update = cur.fetchall()
        updated_count = 0
        
        for question_id, old_image_url in questions_to_update:
            if old_image_url:
                # 古いURLから画像ファイル名を抽出
                old_url_parts = old_image_url.split('/')
                if len(old_url_parts) > 0:
                    image_filename = old_url_parts[-1]  # 最後の部分がファイル名
                    # 新しいURLを構築
                    new_question_image_url = f"{new_image_url}/{image_filename}"
                    
                    print(f"  問題ID {question_id}:")
                    print(f"    古いURL: {old_image_url}")
                    print(f"    新しいURL: {new_question_image_url}")
                    updated_count += 1
        
        print(f"\n✅ シミュレーション完了: {updated_count}件の問題の画像URLが更新されます")
        
        # 7. 実際の更新処理（コメントアウト）
        print("\n7. 実際の更新処理（テスト用のためコメントアウト）")
        print("実際に更新する場合は、以下のコードのコメントアウトを解除してください:")
        print("""
        # 教材のWasabiフォルダパスを更新
        cur.execute('''
            UPDATE social_studies_textbooks 
            SET wasabi_folder_path = %s 
            WHERE id = %s
        ''', (wasabi_folder_path, test_textbook_id))
        
        # 問題の画像URLを更新
        for question_id, old_image_url in questions_to_update:
            if old_image_url:
                old_url_parts = old_image_url.split('/')
                if len(old_url_parts) > 0:
                    image_filename = old_url_parts[-1]
                    new_question_image_url = f"{new_image_url}/{image_filename}"
                    
                    cur.execute('''
                        UPDATE social_studies_questions
                        SET image_url = %s
                        WHERE id = %s
                    ''', (new_question_image_url, question_id))
        
        conn.commit()
        print(f"✅ 更新完了: 教材パスと{updated_count}件の問題の画像URLを更新しました")
        """)
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    test_image_path_update() 