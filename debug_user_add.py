#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

def debug_user_addition():
    """ユーザー追加のデバッグ"""
    db_path = 'flashcards.db'
    
    print("🔍 ユーザー追加デバッグ開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        # データベースに接続
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 現在のユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        initial_count = cur.fetchone()[0]
        print(f"📊 追加前のユーザー数: {initial_count}")
        
        # テストユーザーを追加
        test_username = f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        test_full_name = "テストユーザー"
        test_password = "test123"
        hashed_password = generate_password_hash(test_password)
        
        print(f"➕ テストユーザーを追加: {test_username}")
        
        cur.execute('''
            INSERT INTO users (username, email, password_hash, is_admin, full_name, grade, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (test_username, hashed_password, False, test_full_name, ''))
        
        user_id = cur.lastrowid
        print(f"✅ ユーザー追加完了: ID={user_id}")
        
        # コミット
        conn.commit()
        print("💾 データベースコミット完了")
        
        # 追加後のユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        final_count = cur.fetchone()[0]
        print(f"📊 追加後のユーザー数: {final_count}")
        
        # 追加されたユーザーを確認
        cur.execute('SELECT id, username, full_name, created_at FROM users WHERE id = ?', (user_id,))
        user = cur.fetchone()
        if user:
            print(f"✅ 追加されたユーザー確認: ID={user[0]}, ユーザー名={user[1]}, 表示名={user[2]}, 作成日時={user[3]}")
        else:
            print("❌ 追加されたユーザーが見つかりません")
        
        conn.close()
        print("🔍 デバッグ完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    debug_user_addition() 