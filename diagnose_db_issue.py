#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import time
from datetime import datetime
import stat

def check_file_info(filepath):
    """ファイルの詳細情報を取得"""
    if not os.path.exists(filepath):
        return None
    
    stat_info = os.stat(filepath)
    return {
        'exists': True,
        'size': stat_info.st_size,
        'modified': datetime.fromtimestamp(stat_info.st_mtime),
        'permissions': oct(stat_info.st_mode)[-3:],
        'readable': os.access(filepath, os.R_OK),
        'writable': os.access(filepath, os.W_OK),
        'executable': os.access(filepath, os.X_OK)
    }

def check_database_state(db_path):
    """データベースの状態を詳細にチェック"""
    print(f"\n🔍 データベースファイル詳細チェック: {db_path}")
    print("=" * 60)
    
    # ファイル情報
    file_info = check_file_info(db_path)
    if not file_info:
        print(f"❌ ファイルが存在しません: {db_path}")
        return False
    
    print(f"✅ ファイル存在: {file_info['exists']}")
    print(f"📏 ファイルサイズ: {file_info['size']:,} bytes")
    print(f"📅 最終更新: {file_info['modified']}")
    print(f"🔐 パーミッション: {file_info['permissions']}")
    print(f"📖 読み取り可能: {file_info['readable']}")
    print(f"✏️  書き込み可能: {file_info['writable']}")
    print(f"⚙️  実行可能: {file_info['executable']}")
    
    # SQLiteデータベースの詳細チェック
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # PRAGMA情報
        print(f"\n📊 SQLite PRAGMA情報:")
        pragmas = [
            'journal_mode', 'synchronous', 'cache_size', 'temp_store',
            'foreign_keys', 'locking_mode', 'busy_timeout'
        ]
        
        for pragma in pragmas:
            try:
                cursor.execute(f'PRAGMA {pragma}')
                result = cursor.fetchone()
                print(f"  {pragma}: {result[0] if result else 'N/A'}")
            except Exception as e:
                print(f"  {pragma}: エラー - {e}")
        
        # テーブル一覧
        print(f"\n📋 テーブル一覧:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # usersテーブルの詳細
        if any('users' in table for table in tables):
            print(f"\n👥 usersテーブル詳細:")
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            print(f"  カラム数: {len(columns)}")
            for col in columns:
                print(f"    {col[1]} ({col[2]}) - NOT NULL: {col[3]}, PK: {col[5]}")
            
            # ユーザー数
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"  ユーザー数: {user_count}")
            
            # 最新のユーザー
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
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ データベース接続エラー: {e}")
        return False

def test_database_write(db_path):
    """データベースへの書き込みテスト"""
    print(f"\n🧪 データベース書き込みテスト")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # テスト用テーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS write_test (
                id INTEGER PRIMARY KEY,
                test_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # テストデータ挿入
        test_data = f"write_test_{int(time.time())}"
        cursor.execute("INSERT INTO write_test (test_data) VALUES (?)", (test_data,))
        test_id = cursor.lastrowid
        
        # コミット
        conn.commit()
        print(f"✅ テストデータ挿入成功: ID={test_id}, データ={test_data}")
        
        # 確認
        cursor.execute("SELECT * FROM write_test WHERE id = ?", (test_id,))
        result = cursor.fetchone()
        if result:
            print(f"✅ テストデータ確認成功: {result}")
        else:
            print(f"❌ テストデータ確認失敗")
        
        # クリーンアップ
        cursor.execute("DELETE FROM write_test WHERE id = ?", (test_id,))
        conn.commit()
        print(f"✅ テストデータ削除完了")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 書き込みテストエラー: {e}")
        return False

def check_environment():
    """環境変数とパスの確認"""
    print(f"\n🌍 環境変数とパス確認")
    print("=" * 40)
    
    print(f"現在の作業ディレクトリ: {os.getcwd()}")
    print(f"DB_TYPE: {os.getenv('DB_TYPE', '未設定')}")
    print(f"DB_PATH: {os.getenv('DB_PATH', '未設定')}")
    
    # 絶対パスでのDB_PATH
    db_path = os.path.abspath(os.getenv('DB_PATH', 'flashcards.db'))
    print(f"絶対パスDB_PATH: {db_path}")
    
    # 同じディレクトリ内の.dbファイル一覧
    current_dir = os.getcwd()
    db_files = [f for f in os.listdir(current_dir) if f.endswith('.db')]
    print(f"現在ディレクトリの.dbファイル: {db_files}")

def main():
    print("🔧 データベース問題診断ツール")
    print("=" * 60)
    
    # 環境確認
    check_environment()
    
    # データベースパス
    db_path = os.path.abspath(os.getenv('DB_PATH', 'flashcards.db'))
    
    # ファイル情報チェック
    file_info = check_file_info(db_path)
    if not file_info:
        print(f"\n❌ データベースファイルが見つかりません: {db_path}")
        print("💡 解決策:")
        print("  1. アプリケーションを一度停止してください")
        print("  2. python init_db.py を実行してデータベースを初期化してください")
        print("  3. アプリケーションを再起動してください")
        return
    
    # データベース状態チェック
    if check_database_state(db_path):
        # 書き込みテスト
        if test_database_write(db_path):
            print(f"\n✅ データベースは正常に動作しています")
        else:
            print(f"\n❌ データベースへの書き込みに問題があります")
    else:
        print(f"\n❌ データベースの状態に問題があります")
    
    print(f"\n📝 推奨される次のステップ:")
    print("  1. アプリケーションを停止してください")
    print("  2. このスクリプトを再実行して結果を確認してください")
    print("  3. 問題が解決しない場合は、python init_db.py でデータベースを再初期化してください")

if __name__ == "__main__":
    main() 