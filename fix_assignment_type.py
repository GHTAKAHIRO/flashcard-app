#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def fix_assignment_type_column():
    """assignment_typeカラムを追加"""
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
        
        # 現在のカラム一覧を確認
        print("\n🔍 現在のtextbook_assignmentsテーブルのカラムを確認...")
        cur.execute("PRAGMA table_info(textbook_assignments)")
        columns = cur.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"現在のカラム: {column_names}")
        
        # assignment_typeカラムの存在確認
        if 'assignment_type' not in column_names:
            print("\n➕ assignment_typeカラムを追加中...")
            
            # assignment_typeカラムを追加
            cur.execute("ALTER TABLE textbook_assignments ADD COLUMN assignment_type TEXT")
            
            # 既存データをstudy_typeからコピー
            if 'study_type' in column_names:
                cur.execute("UPDATE textbook_assignments SET assignment_type = study_type WHERE assignment_type IS NULL")
                print("既存データをstudy_typeからコピーしました")
            
            conn.commit()
            print("✅ assignment_typeカラム追加完了")
            
            # 追加後の確認
            cur.execute("PRAGMA table_info(textbook_assignments)")
            new_columns = cur.fetchall()
            new_column_names = [col[1] for col in new_columns]
            print(f"追加後のカラム: {new_column_names}")
            
        else:
            print("✅ assignment_typeカラムは既に存在します")
        
        conn.close()
        print("\n✅ assignment_typeカラム修正完了")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    fix_assignment_type_column() 