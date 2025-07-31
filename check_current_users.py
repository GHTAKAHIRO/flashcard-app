#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def check_current_users():
    """現在のユーザー一覧を確認"""
    db_path = 'flashcards.db'
    
    print("👥 現在のユーザー一覧確認")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # ユーザー数を確認
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        print(f"\n📊 ユーザー数: {user_count}")
        
        # 全ユーザー一覧
        cur.execute('''
            SELECT id, username, full_name, is_admin, created_at 
            FROM users 
            ORDER BY created_at DESC
        ''')
        
        users = cur.fetchall()
        if users:
            print(f"\n📋 ユーザー一覧:")
            for user in users:
                print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日時: {user[4]}")
        else:
            print("❌ ユーザーが見つかりません")
        
        # 最新のユーザーを詳しく確認
        if users:
            latest_user = users[0]
            print(f"\n🔍 最新のユーザー詳細:")
            print(f"  ID: {latest_user[0]}")
            print(f"  ユーザー名: {latest_user[1]}")
            print(f"  表示名: {latest_user[2]}")
            print(f"  管理者権限: {latest_user[3]}")
            print(f"  作成日時: {latest_user[4]}")
        
        conn.close()
        print("\n✅ ユーザー確認完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    check_current_users() 