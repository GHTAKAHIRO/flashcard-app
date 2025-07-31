#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

def fix_admin_and_debug():
    """管理者ログインを修正し、ユーザー追加をデバッグ"""
    db_path = 'flashcards.db'
    
    print("🔧 管理者ログイン修正とデバッグ開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 1. 管理者ユーザーの確認と修正
        print("\n🔍 管理者ユーザーの確認...")
        cur.execute('SELECT id, username, password_hash, is_admin, full_name FROM users WHERE username = ?', ('admin',))
        admin_user = cur.fetchone()
        
        if admin_user:
            user_id, username, password_hash, is_admin, full_name = admin_user
            print(f"👤 管理者ユーザー: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}, 表示名={full_name}")
            print(f"🔑 現在のパスワードハッシュ: {password_hash[:50]}...")
            
            # パスワードをリセット
            new_password = 'admin'
            new_hash = generate_password_hash(new_password)
            cur.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
            print(f"✅ 管理者パスワードをリセット: {new_password}")
        else:
            print("❌ 管理者ユーザーが見つかりません")
        
        # 2. 現在のユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        initial_count = cur.fetchone()[0]
        print(f"\n📊 現在のユーザー数: {initial_count}")
        
        # 3. テストユーザーを追加
        print("\n➕ テストユーザーを追加...")
        test_username = 'test_user_debug'
        test_full_name = 'テストユーザー'
        test_password = 'test123'
        test_hash = generate_password_hash(test_password)
        
        # 既存のテストユーザーを削除
        cur.execute('DELETE FROM users WHERE username = ?', (test_username,))
        
        # 新しいテストユーザーを追加
        cur.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, full_name, grade, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (test_username, test_hash, False, test_full_name, ''))
        
        new_user_id = cur.lastrowid
        print(f"✅ テストユーザー追加完了: ID={new_user_id}")
        
        # 4. コミット
        conn.commit()
        print("💾 データベースコミット完了")
        
        # 5. 追加後の確認
        cur.execute('SELECT COUNT(*) FROM users')
        final_count = cur.fetchone()[0]
        print(f"📊 追加後のユーザー数: {final_count}")
        
        # 6. 追加されたユーザーを確認
        cur.execute('SELECT id, username, full_name, created_at FROM users WHERE id = ?', (new_user_id,))
        user = cur.fetchone()
        if user:
            print(f"✅ 追加されたユーザー確認: ID={user[0]}, ユーザー名={user[1]}, 表示名={user[2]}, 作成日時={user[3]}")
        else:
            print("❌ 追加されたユーザーが見つかりません")
        
        # 7. 最新のユーザー一覧
        print(f"\n👥 最新のユーザー一覧:")
        cur.execute('''
            SELECT id, username, full_name, is_admin, created_at 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        users = cur.fetchall()
        for user in users:
            print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日時: {user[4]}")
        
        conn.close()
        print("\n✅ 修正とデバッグ完了")
        print("\n📝 次のステップ:")
        print("1. 管理者ログイン: ユーザー名=admin, パスワード=admin")
        print("2. ブラウザで管理画面にアクセス")
        print("3. ユーザー追加を試してください")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    fix_admin_and_debug() 