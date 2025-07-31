#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def check_database_direct():
    """データベースを直接確認"""
    db_path = 'flashcards.db'
    
    print("🔍 データベース直接確認開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # テーブル一覧を確認
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        print(f"\n📋 テーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # usersテーブルの構造を確認
        print(f"\n🏗️ usersテーブルの構造:")
        cur.execute("PRAGMA table_info(users)")
        columns = cur.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - NOT NULL: {col[3]}, DEFAULT: {col[4]}, PK: {col[5]}")
        
        # ユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        print(f"\n📊 ユーザー数: {user_count}")
        
        # 最新のユーザーを表示
        if user_count > 0:
            cur.execute('''
                SELECT id, username, full_name, is_admin, created_at 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 5
            ''')
            users = cur.fetchall()
            print(f"\n👥 最新のユーザー:")
            for user in users:
                print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日時: {user[4]}")
        
        conn.close()
        print("\n✅ データベース確認完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    check_database_direct() 