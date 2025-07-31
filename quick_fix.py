#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash

def quick_fix():
    """データベースの問題を素早く修正"""
    db_path = 'flashcards.db'
    
    print("🔧 クイック修正開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 1. 管理者パスワードをリセット
        print("\n🔑 管理者パスワードをリセット...")
        new_password = 'admin'
        new_hash = generate_password_hash(new_password)
        cur.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))
        print(f"✅ 管理者パスワードをリセット: {new_password}")
        
        # 2. assignment_typeカラムを追加
        print("\n➕ assignment_typeカラムを追加...")
        try:
            cur.execute('ALTER TABLE textbook_assignments ADD COLUMN assignment_type TEXT DEFAULT "both"')
            print("✅ assignment_typeカラムを追加しました")
            
            # 既存のデータをstudy_typeからassignment_typeにコピー
            cur.execute('UPDATE textbook_assignments SET assignment_type = study_type WHERE assignment_type IS NULL')
            print("✅ 既存データをstudy_typeからassignment_typeにコピーしました")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("✅ assignment_typeカラムは既に存在します")
            else:
                raise e
        
        # 3. コミット
        conn.commit()
        print("💾 データベースコミット完了")
        
        # 4. 確認
        print("\n📊 修正後の確認:")
        
        # 管理者ユーザーの確認
        cur.execute('SELECT id, username, is_admin FROM users WHERE username = ?', ('admin',))
        admin = cur.fetchone()
        if admin:
            print(f"✅ 管理者ユーザー: ID={admin[0]}, ユーザー名={admin[1]}, 管理者権限={admin[2]}")
        
        # ユーザー数の確認
        cur.execute('SELECT COUNT(*) FROM users')
        user_count = cur.fetchone()[0]
        print(f"📊 ユーザー数: {user_count}")
        
        # textbook_assignmentsテーブルの確認
        cur.execute("PRAGMA table_info(textbook_assignments)")
        columns = [col[1] for col in cur.fetchall()]
        if 'assignment_type' in columns:
            print("✅ assignment_typeカラムが存在します")
        
        conn.close()
        print("\n✅ クイック修正完了")
        print("\n📝 次のステップ:")
        print("1. 管理者ログイン: ユーザー名=admin, パスワード=admin")
        print("2. ブラウザで管理画面にアクセス")
        print("3. ユーザー追加を試してください")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    quick_fix() 