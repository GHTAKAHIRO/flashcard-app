#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import time
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_path():
    """データベースパスを取得"""
    return os.path.abspath(os.getenv('DB_PATH', 'flashcards.db'))

def check_user_before_test():
    """テスト前のユーザー状態を確認"""
    print("🔍 テスト前のユーザー状態確認")
    print("=" * 40)
    
    db_path = get_db_path()
    print(f"データベースパス: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # 現在のユーザー数
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"現在のユーザー数: {user_count}")
        
        # 最新のユーザー
        if user_count > 0:
            cursor.execute("""
                SELECT id, username, full_name, is_admin, created_at 
                FROM users 
                ORDER BY id DESC 
                LIMIT 3
            """)
            recent_users = cursor.fetchall()
            print(f"最新のユーザー（上位3件）:")
            for user in recent_users:
                print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日: {user[4]}")
        
        conn.close()
        return user_count
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return 0

def test_user_registration():
    """ユーザー登録テスト"""
    print(f"\n🧪 ユーザー登録テスト開始")
    print("=" * 40)
    
    db_path = get_db_path()
    test_username = f"test_user_{int(time.time())}"
    test_password = "test123"
    test_full_name = f"テストユーザー {int(time.time())}"
    
    print(f"テストユーザー名: {test_username}")
    print(f"テストパスワード: {test_password}")
    print(f"テスト表示名: {test_full_name}")
    
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # ユーザー名の重複チェック
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (test_username,))
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            print(f"⚠️  テストユーザー名が既に存在します: {test_username}")
            return False
        
        # パスワードハッシュ生成
        hashed_password = generate_password_hash(test_password, method='pbkdf2:sha256')
        print(f"パスワードハッシュ: {hashed_password[:50]}...")
        
        # ユーザー登録前の確認
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count_before = cursor.fetchone()[0]
        print(f"登録前のユーザー数: {user_count_before}")
        
        # ユーザー登録
        print(f"ユーザー登録実行中...")
        insert_sql = '''
            INSERT INTO users (username, email, password_hash, is_admin, full_name, grade, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        cursor.execute(insert_sql, (test_username, hashed_password, False, test_full_name, 'test'))
        
        # 登録後のユーザーID取得
        user_id = cursor.lastrowid
        print(f"登録されたユーザーID: {user_id}")
        
        # コミット前の確認
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (test_username,))
        count_before_commit = cursor.fetchone()[0]
        print(f"コミット前のユーザー数（該当ユーザー）: {count_before_commit}")
        
        # コミット
        print(f"データベースコミット実行中...")
        conn.commit()
        print(f"✅ コミット完了")
        
        # コミット後の確認
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (test_username,))
        count_after_commit = cursor.fetchone()[0]
        print(f"コミット後のユーザー数（該当ユーザー）: {count_after_commit}")
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count_after = cursor.fetchone()[0]
        print(f"コミット後の総ユーザー数: {user_count_after}")
        
        # 登録されたユーザーの詳細確認
        cursor.execute("""
            SELECT id, username, full_name, is_admin, created_at 
            FROM users 
            WHERE username = ?
        """, (test_username,))
        registered_user = cursor.fetchone()
        
        if registered_user:
            print(f"✅ ユーザー登録成功:")
            print(f"  ID: {registered_user[0]}")
            print(f"  ユーザー名: {registered_user[1]}")
            print(f"  表示名: {registered_user[2]}")
            print(f"  管理者: {registered_user[3]}")
            print(f"  作成日: {registered_user[4]}")
        else:
            print(f"❌ ユーザー登録失敗: データが見つかりません")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ユーザー登録エラー: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")
        return False

def test_user_login(test_username, test_password):
    """ユーザーログインテスト"""
    print(f"\n🔐 ユーザーログインテスト")
    print("=" * 40)
    
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # ユーザー検索
        cursor.execute("""
            SELECT id, username, password_hash, is_admin 
            FROM users 
            WHERE username = ?
        """, (test_username,))
        user_data = cursor.fetchone()
        
        if not user_data:
            print(f"❌ ユーザーが見つかりません: {test_username}")
            return False
        
        user_id, username, password_hash, is_admin = user_data
        print(f"ユーザー情報:")
        print(f"  ID: {user_id}")
        print(f"  ユーザー名: {username}")
        print(f"  管理者: {is_admin}")
        print(f"  パスワードハッシュ: {password_hash[:50]}...")
        
        # パスワード検証
        if check_password_hash(password_hash, test_password):
            print(f"✅ パスワード検証成功")
            print(f"✅ ログイン成功: user_id={user_id}, username={username}")
            return True
        else:
            print(f"❌ パスワード検証失敗")
            return False
        
    except Exception as e:
        print(f"❌ ログインテストエラー: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def cleanup_test_user(test_username):
    """テストユーザーの削除"""
    print(f"\n🧹 テストユーザー削除")
    print("=" * 40)
    
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # 削除前の確認
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (test_username,))
        count_before = cursor.fetchone()[0]
        print(f"削除前のユーザー数（該当ユーザー）: {count_before}")
        
        if count_before > 0:
            # ユーザー削除
            cursor.execute("DELETE FROM users WHERE username = ?", (test_username,))
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"✅ 削除完了: {deleted_count}件")
            
            # 削除後の確認
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (test_username,))
            count_after = cursor.fetchone()[0]
            print(f"削除後のユーザー数（該当ユーザー）: {count_after}")
        else:
            print(f"⚠️  削除対象のユーザーが見つかりません")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 削除エラー: {e}")

def main():
    print("🔧 ユーザー登録・ログインテストツール")
    print("=" * 60)
    
    # テスト前の状態確認
    initial_user_count = check_user_before_test()
    
    # テストユーザー情報
    test_username = f"test_user_{int(time.time())}"
    test_password = "test123"
    
    # ユーザー登録テスト
    if test_user_registration():
        print(f"\n✅ ユーザー登録テスト成功")
        
        # 少し待機
        print(f"⏳ 3秒待機中...")
        time.sleep(3)
        
        # ログインテスト
        if test_user_login(test_username, test_password):
            print(f"\n✅ ログインテスト成功")
        else:
            print(f"\n❌ ログインテスト失敗")
        
        # クリーンアップ
        cleanup_test_user(test_username)
        
    else:
        print(f"\n❌ ユーザー登録テスト失敗")
    
    # テスト後の状態確認
    print(f"\n🔍 テスト後のユーザー状態確認")
    print("=" * 40)
    final_user_count = check_user_before_test()
    
    print(f"\n📊 テスト結果サマリー:")
    print(f"  テスト前のユーザー数: {initial_user_count}")
    print(f"  テスト後のユーザー数: {final_user_count}")
    print(f"  ユーザー数の変化: {final_user_count - initial_user_count}")

if __name__ == "__main__":
    main() 