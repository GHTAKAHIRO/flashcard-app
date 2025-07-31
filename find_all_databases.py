#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import glob
from datetime import datetime

def find_all_database_files():
    """プロジェクト内のすべてのデータベースファイルを検索"""
    print("🔍 プロジェクト内のデータベースファイル検索")
    print("=" * 60)
    
    # 現在のディレクトリとサブディレクトリを検索
    db_files = []
    
    # 現在のディレクトリ
    current_dir = os.getcwd()
    print(f"検索ディレクトリ: {current_dir}")
    
    # .dbファイルを検索
    for root, dirs, files in os.walk(current_dir):
        for file in files:
            if file.endswith('.db'):
                full_path = os.path.join(root, file)
                db_files.append(full_path)
    
    if not db_files:
        print("❌ データベースファイルが見つかりません")
        return []
    
    print(f"✅ 見つかったデータベースファイル: {len(db_files)}件")
    for i, db_file in enumerate(db_files, 1):
        print(f"  {i}. {db_file}")
    
    return db_files

def analyze_database_file(db_path):
    """データベースファイルの詳細分析"""
    print(f"\n📊 データベース分析: {os.path.basename(db_path)}")
    print("-" * 50)
    
    try:
        # ファイル情報
        stat_info = os.stat(db_path)
        print(f"📏 サイズ: {stat_info.st_size:,} bytes")
        print(f"📅 最終更新: {datetime.fromtimestamp(stat_info.st_mtime)}")
        
        # SQLite接続
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"📋 テーブル数: {len(table_names)}")
        for table in table_names:
            print(f"  - {table}")
        
        # usersテーブルの詳細
        if 'users' in table_names:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"👥 ユーザー数: {user_count}")
            
            if user_count > 0:
                # 最新のユーザー
                cursor.execute("""
                    SELECT id, username, full_name, is_admin, created_at 
                    FROM users 
                    ORDER BY id DESC 
                    LIMIT 3
                """)
                recent_users = cursor.fetchall()
                print(f"📝 最新のユーザー:")
                for user in recent_users:
                    print(f"    ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日: {user[4]}")
        
        # textbook_assignmentsテーブルの詳細
        if 'textbook_assignments' in table_names:
            cursor.execute("SELECT COUNT(*) FROM textbook_assignments")
            assignment_count = cursor.fetchone()[0]
            print(f"📚 テキストブック割り当て数: {assignment_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 分析エラー: {e}")
        return False

def check_database_consistency():
    """複数のデータベースファイル間の一貫性をチェック"""
    print(f"\n🔄 データベース一貫性チェック")
    print("=" * 50)
    
    db_files = find_all_database_files()
    if len(db_files) <= 1:
        print("✅ データベースファイルは1つだけです")
        return
    
    print(f"⚠️  複数のデータベースファイルが見つかりました")
    
    # 各データベースファイルを分析
    db_info = []
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # usersテーブルのユーザー数
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # 最新のユーザー
            cursor.execute("SELECT username, created_at FROM users ORDER BY id DESC LIMIT 1")
            latest_user = cursor.fetchone()
            
            db_info.append({
                'path': db_path,
                'user_count': user_count,
                'latest_user': latest_user
            })
            
            conn.close()
            
        except Exception as e:
            print(f"❌ {db_path} の分析エラー: {e}")
    
    # 結果を比較
    print(f"\n📊 データベース比較結果:")
    for i, info in enumerate(db_info, 1):
        print(f"\n  {i}. {os.path.basename(info['path'])}")
        print(f"     ユーザー数: {info['user_count']}")
        if info['latest_user']:
            print(f"     最新ユーザー: {info['latest_user'][0]} ({info['latest_user'][1]})")
        else:
            print(f"     最新ユーザー: なし")

def main():
    print("🔧 データベースファイル検索・分析ツール")
    print("=" * 60)
    
    # すべてのデータベースファイルを検索
    db_files = find_all_database_files()
    
    if not db_files:
        print("\n💡 推奨される解決策:")
        print("  1. python init_db.py を実行してデータベースを初期化してください")
        print("  2. アプリケーションを再起動してください")
        return
    
    # 各データベースファイルを分析
    for db_path in db_files:
        analyze_database_file(db_path)
    
    # 一貫性チェック
    check_database_consistency()
    
    print(f"\n📝 推奨される次のステップ:")
    if len(db_files) > 1:
        print("⚠️  複数のデータベースファイルが見つかりました")
        print("  1. どのファイルが正しいデータベースかを確認してください")
        print("  2. 不要なファイルを削除してください")
        print("  3. アプリケーションが正しいファイルを参照しているか確認してください")
    else:
        print("✅ データベースファイルは1つだけです")
        print("  1. アプリケーションがこのファイルを正しく参照しているか確認してください")
        print("  2. ファイルのパーミッションを確認してください")

if __name__ == "__main__":
    main() 