#!/usr/bin/env python3
"""
本番環境のデータをローカルに同期するスクリプト
"""

import os
import sqlite3
import shutil
from datetime import datetime

def sync_production_data():
    """本番環境のデータをローカルに同期"""
    
    print("🔄 本番環境データ同期")
    print("=" * 50)
    
    # 本番環境のデータベースパス
    production_db = "/opt/render/project/src/flashcards.db"
    local_db = "flashcards.db"
    
    # 本番環境のデータベースが存在するかチェック
    if os.path.exists(production_db):
        print(f"📁 本番環境データベース発見: {production_db}")
        
        try:
            # 本番環境のデータベースをローカルにコピー
            shutil.copy2(production_db, local_db)
            print(f"✅ データベース同期完了: {local_db}")
            
            # 同期後のデータ確認
            conn = sqlite3.connect(local_db)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            print(f"\n👥 同期後のユーザー数: {user_count}")
            
            if user_count > 0:
                cursor.execute('''
                    SELECT id, username, full_name, is_admin, created_at
                    FROM users 
                    ORDER BY id DESC 
                    LIMIT 5
                ''')
                users = cursor.fetchall()
                
                print(f"\n📊 同期されたユーザー（上位{len(users)}件）:")
                for user in users:
                    user_id, username, full_name, is_admin, created_at = user
                    admin_status = "✅" if is_admin else "❌"
                    full_name = full_name or "未設定"
                    print(f"  - ID: {user_id}, ユーザー名: {username}, 表示名: {full_name}, 管理者: {admin_status}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 同期エラー: {e}")
            return False
            
    else:
        print(f"❌ 本番環境データベースが見つかりません: {production_db}")
        print("💡 本番環境でアプリケーションが起動していない可能性があります")
        return False
    
    return True

def check_data_consistency():
    """データの整合性をチェック"""
    
    print("\n🔍 データ整合性チェック")
    print("=" * 30)
    
    try:
        conn = sqlite3.connect("flashcards.db")
        cursor = conn.cursor()
        
        # 各テーブルのデータ数を確認
        tables = ['users', 'input_textbooks', 'input_units', 'input_questions']
        
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count}件")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 整合性チェックエラー: {e}")

if __name__ == "__main__":
    if sync_production_data():
        check_data_consistency()
        print("\n✅ 同期処理完了")
    else:
        print("\n❌ 同期処理失敗") 