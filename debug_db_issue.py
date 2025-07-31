#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import time
from werkzeug.security import generate_password_hash

def debug_db_issue():
    """データベースの問題を詳しく調査"""
    db_path = 'flashcards.db'
    
    print("🔍 データベース問題調査開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    # ファイル情報
    stat = os.stat(db_path)
    print(f"📊 ファイルサイズ: {stat.st_size} bytes")
    print(f"📅 最終更新: {time.ctime(stat.st_mtime)}")
    
    try:
        # 1. 基本的な接続テスト
        print("\n🔌 基本的な接続テスト...")
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 2. 現在のユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        print(f"📊 現在のユーザー数: {user_count}")
        
        # 3. ユーザー一覧
        cur.execute('SELECT id, username, full_name, created_at FROM users ORDER BY id')
        users = cur.fetchall()
        print(f"\n👥 現在のユーザー一覧:")
        for user in users:
            print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 作成日時: {user[3]}")
        
        # 4. テストユーザーを追加
        print(f"\n➕ テストユーザーを追加...")
        test_username = f"test_debug_{int(time.time())}"
        test_full_name = "テストユーザー"
        test_password = "test123"
        hashed_password = generate_password_hash(test_password)
        
        # 追加前の確認
        cur.execute('SELECT COUNT(*) FROM users WHERE username = ?', (test_username,))
        count_before = cur.fetchone()[0]
        print(f"追加前のユーザー数: {count_before}")
        
        # INSERT実行
        cur.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, full_name, grade, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (test_username, hashed_password, False, test_full_name, ''))
        
        user_id = cur.lastrowid
        print(f"INSERT完了: user_id={user_id}")
        
        # コミット前の確認
        cur.execute('SELECT COUNT(*) FROM users WHERE username = ?', (test_username,))
        count_after_insert = cur.fetchone()[0]
        print(f"INSERT後のユーザー数: {count_after_insert}")
        
        # コミット
        print("コミット開始...")
        conn.commit()
        print("コミット完了")
        
        # コミット後の確認
        cur.execute('SELECT COUNT(*) FROM users WHERE username = ?', (test_username,))
        count_after_commit = cur.fetchone()[0]
        print(f"コミット後のユーザー数: {count_after_commit}")
        
        # 追加されたユーザーの確認
        cur.execute('SELECT id, username, full_name, created_at FROM users WHERE username = ?', (test_username,))
        added_user = cur.fetchone()
        if added_user:
            print(f"✅ 追加されたユーザー確認: ID={added_user[0]}, ユーザー名={added_user[1]}, 表示名={added_user[2]}, 作成日時={added_user[3]}")
        else:
            print("❌ 追加されたユーザーが見つかりません")
        
        # 5. 最終確認
        cur.execute('SELECT COUNT(*) FROM users')
        final_count = cur.fetchone()[0]
        print(f"\n📊 最終ユーザー数: {final_count}")
        
        # 6. データベースの状態確認
        print(f"\n🔧 データベース状態確認:")
        cur.execute("PRAGMA journal_mode")
        journal_mode = cur.fetchone()[0]
        print(f"ジャーナルモード: {journal_mode}")
        
        cur.execute("PRAGMA synchronous")
        synchronous = cur.fetchone()[0]
        print(f"同期モード: {synchronous}")
        
        cur.execute("PRAGMA foreign_keys")
        foreign_keys = cur.fetchone()[0]
        print(f"外部キー制約: {foreign_keys}")
        
        conn.close()
        print("\n✅ データベース問題調査完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    debug_db_issue() 