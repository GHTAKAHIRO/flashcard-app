#!/usr/bin/env python3
"""
本番環境のユーザーデータ確認スクリプト
"""

import os
import sqlite3
from datetime import datetime

def check_production_users():
    """本番環境のユーザーデータを確認"""
    
    print("🔍 本番環境ユーザーデータ確認")
    print("=" * 50)
    
    # データベースパス（本番環境）
    db_path = "/opt/render/project/src/flashcards.db"
    
    # ローカル環境の場合は現在のパスを使用
    if not os.path.exists(db_path):
        db_path = "flashcards.db"
        print(f"📁 ローカル環境のデータベースを使用: {db_path}")
    else:
        print(f"📁 本番環境のデータベースを使用: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ユーザー数を確認
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        print(f"\n👥 総ユーザー数: {user_count}")
        
        if user_count > 0:
            # 最新のユーザーを表示
            cursor.execute('''
                SELECT id, username, full_name, is_admin, created_at, last_login
                FROM users 
                ORDER BY id DESC 
                LIMIT 10
            ''')
            users = cursor.fetchall()
            
            print(f"\n📊 最新ユーザー（上位{len(users)}件）:")
            print("-" * 80)
            print(f"{'ID':<4} {'ユーザー名':<15} {'表示名':<15} {'管理者':<8} {'作成日時':<20} {'最終ログイン':<20}")
            print("-" * 80)
            
            for user in users:
                user_id, username, full_name, is_admin, created_at, last_login = user
                admin_status = "✅" if is_admin else "❌"
                full_name = full_name or "未設定"
                
                # 日時フォーマット
                created_str = str(created_at)[:19] if created_at else "未設定"
                login_str = str(last_login)[:19] if last_login else "未ログイン"
                
                print(f"{user_id:<4} {username:<15} {full_name:<15} {admin_status:<8} {created_str:<20} {login_str:<20}")
        
        # データベースファイルの情報
        file_size = os.path.getsize(db_path)
        file_time = datetime.fromtimestamp(os.path.getmtime(db_path))
        
        print(f"\n📁 データベースファイル情報:")
        print(f"  サイズ: {file_size:,} bytes")
        print(f"  最終更新: {file_time}")
        
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\n📋 テーブル一覧 ({len(tables)}件):")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count}件")
        
        conn.close()
        print(f"\n✅ データ確認完了")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_production_users() 