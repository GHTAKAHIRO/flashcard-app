#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import shutil
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def backup_database():
    """データベースのバックアップを作成"""
    print("💾 データベースバックアップ作成")
    print("=" * 40)
    
    db_path = 'flashcards.db'
    backup_path = f"flashcards_backup_{int(datetime.now().timestamp())}.db"
    
    if os.path.exists(db_path):
        try:
            shutil.copy2(db_path, backup_path)
            print(f"✅ バックアップ作成完了: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ バックアップ作成エラー: {e}")
            return None
    else:
        print(f"⚠️  データベースファイルが見つかりません: {db_path}")
        return None

def fix_assignment_type_column():
    """assignment_typeカラムを追加"""
    print("\n🔧 assignment_typeカラム修正")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('flashcards.db')
        cursor = conn.cursor()
        
        # 現在のカラム一覧を確認
        cursor.execute("PRAGMA table_info(textbook_assignments)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'assignment_type' not in column_names:
            print("assignment_typeカラムを追加中...")
            
            # assignment_typeカラムを追加
            cursor.execute("ALTER TABLE textbook_assignments ADD COLUMN assignment_type TEXT")
            
            # 既存データをstudy_typeからコピー
            if 'study_type' in column_names:
                cursor.execute("UPDATE textbook_assignments SET assignment_type = study_type WHERE assignment_type IS NULL")
                print("既存データをstudy_typeからコピーしました")
            
            conn.commit()
            print("✅ assignment_typeカラム追加完了")
        else:
            print("✅ assignment_typeカラムは既に存在します")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ assignment_typeカラム修正エラー: {e}")
        return False

def fix_admin_password():
    """管理者パスワードを修正"""
    print("\n🔑 管理者パスワード修正")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('flashcards.db')
        cursor = conn.cursor()
        
        # adminユーザーの存在確認
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        
        if not admin_user:
            print("❌ adminユーザーが見つかりません")
            return False
        
        user_id, username, current_hash = admin_user
        print(f"管理者ユーザー: ID={user_id}, ユーザー名={username}")
        print(f"現在のハッシュ: {current_hash[:50]}...")
        
        # 新しいパスワードハッシュを生成
        new_password = 'admin'
        new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        print(f"新しいパスワード: {new_password}")
        print(f"新しいハッシュ: {new_hash[:50]}...")
        
        # パスワードを更新
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        conn.commit()
        
        # 検証
        if check_password_hash(new_hash, new_password):
            print("✅ パスワード更新成功")
            print("✅ パスワード検証成功")
        else:
            print("❌ パスワード検証失敗")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 管理者パスワード修正エラー: {e}")
        return False

def test_database_connection():
    """データベース接続テスト"""
    print("\n🧪 データベース接続テスト")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('flashcards.db')
        cursor = conn.cursor()
        
        # 基本的なクエリテスト
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ ユーザー数取得成功: {user_count}")
        
        cursor.execute("SELECT COUNT(*) FROM textbook_assignments")
        assignment_count = cursor.fetchone()[0]
        print(f"✅ テキストブック割り当て数取得成功: {assignment_count}")
        
        # 書き込みテスト
        test_table = f"test_table_{int(datetime.now().timestamp())}"
        cursor.execute(f"CREATE TABLE {test_table} (id INTEGER PRIMARY KEY, test_data TEXT)")
        cursor.execute(f"INSERT INTO {test_table} (test_data) VALUES (?)", ("test",))
        cursor.execute(f"SELECT * FROM {test_table}")
        result = cursor.fetchone()
        cursor.execute(f"DROP TABLE {test_table}")
        conn.commit()
        
        if result:
            print("✅ 書き込みテスト成功")
        else:
            print("❌ 書き込みテスト失敗")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ データベース接続テストエラー: {e}")
        return False

def main():
    print("🔧 データベース問題修正ツール")
    print("=" * 60)
    
    # バックアップ作成
    backup_path = backup_database()
    
    # assignment_typeカラム修正
    if not fix_assignment_type_column():
        print("\n❌ assignment_typeカラムの修正に失敗しました")
        return
    
    # 管理者パスワード修正
    if not fix_admin_password():
        print("\n❌ 管理者パスワードの修正に失敗しました")
        return
    
    # 接続テスト
    if not test_database_connection():
        print("\n❌ データベース接続テストに失敗しました")
        return
    
    print(f"\n✅ すべての修正が完了しました")
    print(f"\n📝 次のステップ:")
    print(f"  1. アプリケーションを再起動してください")
    print(f"  2. 管理者ログインをテストしてください（ユーザー名: admin, パスワード: admin）")
    print(f"  3. ユーザー登録をテストしてください")
    
    if backup_path:
        print(f"  4. バックアップファイル: {backup_path}")

if __name__ == "__main__":
    main() 