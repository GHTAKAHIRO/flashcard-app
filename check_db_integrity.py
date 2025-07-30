#!/usr/bin/env python3
"""
データベース整合性チェックスクリプト
"""

import sqlite3
import os
from datetime import datetime

def check_database_integrity():
    """データベースの整合性をチェック"""
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print("❌ データベースファイルが見つかりません")
        return
    
    print(f"📁 データベースパス: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # データベースの整合性チェック
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()
        print(f"🔍 整合性チェック結果: {integrity_result[0]}")
        
        if integrity_result[0] != "ok":
            print("❌ データベースに整合性の問題があります")
            return
        
        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        print(f"📋 テーブル一覧: {table_names}")
        
        # 各テーブルのレコード数を確認
        for table_name in table_names:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"📊 {table_name}: {count}件")
            except Exception as e:
                print(f"❌ {table_name}の確認エラー: {e}")
        
        # usersテーブルの詳細確認
        if 'users' in table_names:
            print("\n👥 ユーザーテーブル詳細:")
            cursor.execute("""
                SELECT id, username, is_admin, created_at, last_login 
                FROM users 
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
            
            for user in users:
                print(f"   ID: {user[0]}, ユーザー名: {user[1]}, 管理者: {user[2]}, 作成日: {user[3]}, 最終ログイン: {user[4]}")
        
        # 外部キー制約の確認
        print("\n🔗 外部キー制約の確認:")
        cursor.execute("PRAGMA foreign_key_list(users)")
        foreign_keys = cursor.fetchall()
        if foreign_keys:
            for fk in foreign_keys:
                print(f"   {fk}")
        else:
            print("   外部キー制約は設定されていません")
        
        # データベースファイルの情報
        file_size = os.path.getsize(db_path)
        file_mtime = os.path.getmtime(db_path)
        print(f"\n💾 ファイル情報:")
        print(f"   サイズ: {file_size:,} bytes")
        print(f"   最終更新: {datetime.fromtimestamp(file_mtime)}")
        
    except Exception as e:
        print(f"❌ データベース確認エラー: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    check_database_integrity() 