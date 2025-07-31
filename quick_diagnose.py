#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
from datetime import datetime

def main():
    print("🔧 データベース簡易診断")
    print("=" * 40)
    
    # データベースパス
    db_path = os.path.abspath('flashcards.db')
    print(f"データベースパス: {db_path}")
    
    # ファイル存在確認
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが存在しません")
        return
    
    # ファイル情報
    stat_info = os.stat(db_path)
    print(f"✅ ファイル存在: {db_path}")
    print(f"📏 ファイルサイズ: {stat_info.st_size:,} bytes")
    print(f"📅 最終更新: {datetime.fromtimestamp(stat_info.st_mtime)}")
    
    # 権限確認
    if os.access(db_path, os.R_OK):
        print(f"✅ 読み取り権限: OK")
    else:
        print(f"❌ 読み取り権限: NG")
    
    if os.access(db_path, os.W_OK):
        print(f"✅ 書き込み権限: OK")
    else:
        print(f"❌ 書き込み権限: NG")
    
    # データベース接続テスト
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"\n📋 テーブル一覧:")
        for table in table_names:
            print(f"  - {table}")
        
        # usersテーブルの詳細
        if 'users' in table_names:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"\n👥 ユーザー数: {user_count}")
            
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
        print(f"\n✅ データベース接続成功")
        
    except Exception as e:
        print(f"\n❌ データベース接続エラー: {e}")

if __name__ == "__main__":
    main() 