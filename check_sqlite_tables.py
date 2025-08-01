#!/usr/bin/env python3
"""
SQLiteテーブル構造確認スクリプト
"""

import sqlite3

def check_sqlite_tables():
    """SQLiteデータベースのテーブル構造を確認"""
    try:
        conn = sqlite3.connect('flashcards.db')
        cursor = conn.cursor()
        
        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📋 SQLiteテーブル一覧:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 各テーブルの構造を確認
        for table in tables:
            table_name = table[0]
            print(f"\n🔍 テーブル '{table_name}' の構造:")
            
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # サンプルデータを表示
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print(f"  サンプルデータ: {len(sample_data)}件")
                for row in sample_data:
                    print(f"    {row}")
            else:
                print("  データなし")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == '__main__':
    check_sqlite_tables() 