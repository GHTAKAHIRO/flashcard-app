#!/usr/bin/env python3
"""
データベーステーブル構造更新スクリプト
"""

import sqlite3
import os

def update_database():
    """データベースのテーブル構造を更新"""
    db_path = 'flashcards.db'
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # usersテーブルに不足しているカラムを追加
        updates = [
            # last_loginカラムを追加
            "ALTER TABLE users ADD COLUMN last_login TIMESTAMP",
            # full_nameカラムを追加
            "ALTER TABLE users ADD COLUMN full_name TEXT"
        ]
        
        for update_sql in updates:
            try:
                cursor.execute(update_sql)
                print(f"✅ テーブル更新完了: {update_sql}")
            except Exception as e:
                if "duplicate column name" in str(e):
                    print(f"ℹ️ カラムは既に存在します: {update_sql}")
                else:
                    print(f"❌ テーブル更新エラー: {e}")
        
        # 既存のユーザーにfull_nameを設定
        cursor.execute("UPDATE users SET full_name = username WHERE full_name IS NULL")
        print("✅ 既存ユーザーのfull_nameを更新")
        
        conn.commit()
        print(f"🎉 データベース更新完了: {db_path}")
        
    except Exception as e:
        print(f"❌ データベース更新エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    update_database() 