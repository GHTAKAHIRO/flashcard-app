#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def fix_assignment_type():
    """assignment_typeカラムの問題を修正"""
    db_path = 'flashcards.db'
    
    print("🔧 assignment_typeカラム修正開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 1. textbook_assignmentsテーブルの構造を確認
        print("\n🔍 textbook_assignmentsテーブルの構造確認...")
        cur.execute("PRAGMA table_info(textbook_assignments)")
        columns = cur.fetchall()
        print("現在のカラム:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - NOT NULL: {col[3]}, DEFAULT: {col[4]}, PK: {col[5]}")
        
        # 2. assignment_typeカラムが存在するかチェック
        column_names = [col[1] for col in columns]
        if 'assignment_type' not in column_names:
            print("\n➕ assignment_typeカラムを追加...")
            cur.execute('ALTER TABLE textbook_assignments ADD COLUMN assignment_type TEXT DEFAULT "both"')
            print("✅ assignment_typeカラムを追加しました")
            
            # 既存のデータをstudy_typeからassignment_typeにコピー
            cur.execute('UPDATE textbook_assignments SET assignment_type = study_type WHERE assignment_type IS NULL')
            print("✅ 既存データをstudy_typeからassignment_typeにコピーしました")
        else:
            print("✅ assignment_typeカラムは既に存在します")
        
        # 3. 修正後の構造を確認
        print("\n🔍 修正後のテーブル構造確認...")
        cur.execute("PRAGMA table_info(textbook_assignments)")
        columns = cur.fetchall()
        print("修正後のカラム:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - NOT NULL: {col[3]}, DEFAULT: {col[4]}, PK: {col[5]}")
        
        # 4. データの確認
        cur.execute('SELECT COUNT(*) FROM textbook_assignments')
        count = cur.fetchone()[0]
        print(f"\n📊 textbook_assignmentsテーブルのレコード数: {count}")
        
        if count > 0:
            cur.execute('SELECT id, user_id, textbook_id, study_type, assignment_type FROM textbook_assignments LIMIT 5')
            records = cur.fetchall()
            print("最新のレコード:")
            for record in records:
                print(f"  ID: {record[0]}, ユーザーID: {record[1]}, 教材ID: {record[2]}, study_type: {record[3]}, assignment_type: {record[4]}")
        
        conn.commit()
        print("\n✅ assignment_typeカラム修正完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_assignment_type() 