#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
from datetime import datetime

def check_database_status():
    """データベースの状態を確認"""
    db_path = 'flashcards.db'
    
    print("🔍 データベース状態確認")
    print("=" * 50)
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    # ファイル情報
    stat_info = os.stat(db_path)
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    print(f"📏 ファイルサイズ: {stat_info.st_size:,} bytes")
    print(f"📅 最終更新: {datetime.fromtimestamp(stat_info.st_mtime)}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"\n📋 テーブル一覧 ({len(table_names)}件):")
        for table in table_names:
            print(f"  - {table}")
        
        # usersテーブルの詳細
        if 'users' in table_names:
            print(f"\n👥 usersテーブル詳細:")
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"  ユーザー数: {user_count}")
            
            if user_count > 0:
                cursor.execute("""
                    SELECT id, username, full_name, is_admin, created_at 
                    FROM users 
                    ORDER BY id DESC 
                    LIMIT 5
                """)
                recent_users = cursor.fetchall()
                print(f"  最新のユーザー（上位5件）:")
                for user in recent_users:
                    print(f"    ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日: {user[4]}")
        
        # textbook_assignmentsテーブルの詳細
        if 'textbook_assignments' in table_names:
            print(f"\n📚 textbook_assignmentsテーブル詳細:")
            cursor.execute("SELECT COUNT(*) FROM textbook_assignments")
            assignment_count = cursor.fetchone()[0]
            print(f"  割り当て数: {assignment_count}")
            
            # カラム一覧を確認
            cursor.execute("PRAGMA table_info(textbook_assignments)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            print(f"  カラム: {column_names}")
            
            # assignment_typeカラムの存在確認
            if 'assignment_type' in column_names:
                print(f"  ✅ assignment_typeカラム: 存在")
            else:
                print(f"  ❌ assignment_typeカラム: 存在しない")
        
        # SQLite設定
        print(f"\n⚙️  SQLite設定:")
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        print(f"  ジャーナルモード: {journal_mode}")
        
        cursor.execute("PRAGMA synchronous")
        synchronous = cursor.fetchone()[0]
        print(f"  同期モード: {synchronous}")
        
        cursor.execute("PRAGMA foreign_keys")
        foreign_keys = cursor.fetchone()[0]
        print(f"  外部キー制約: {foreign_keys}")
        
        conn.close()
        print(f"\n✅ データベース状態確認完了")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    check_database_status() 