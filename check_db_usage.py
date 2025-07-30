#!/usr/bin/env python3
"""
データベースの使用量を確認するスクリプト
"""

import psycopg2
import os
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv('dbname.env')

def check_database_usage():
    """データベースの使用量を確認"""
    print("🔍 データベース使用量を確認中...")
    
    try:
        # PostgreSQL接続
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        cursor = conn.cursor()
        print("✅ PostgreSQLデータベースに接続しました")
        
        # データベースサイズを確認
        cursor.execute("""
            SELECT 
                pg_size_pretty(pg_database_size(current_database())) as db_size,
                pg_database_size(current_database()) as db_size_bytes
        """)
        db_info = cursor.fetchone()
        db_size, db_size_bytes = db_info
        
        print(f"📊 データベースサイズ: {db_size}")
        print(f"📊 データベースサイズ（バイト）: {db_size_bytes:,}")
        
        # 各テーブルのサイズを確認
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as table_size,
                pg_total_relation_size(schemaname||'.'||tablename) as table_size_bytes,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes
            FROM pg_stat_user_tables 
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """)
        
        tables = cursor.fetchall()
        
        print("\n📋 テーブル別使用量:")
        print("テーブル名 | サイズ | レコード数（概算） | 操作回数")
        print("-" * 80)
        
        total_size_bytes = 0
        for table in tables:
            schema, table_name, size, size_bytes, inserts, updates, deletes = table
            total_size_bytes += size_bytes
            
            # レコード数を概算（サイズから推定）
            estimated_rows = "不明"
            if size_bytes > 0:
                # 1レコードあたり約1KBと仮定
                estimated_rows = f"{size_bytes // 1024:,}"
            
            print(f"{table_name:15s} | {size:8s} | {estimated_rows:15s} | I:{inserts:6d} U:{updates:6d} D:{deletes:6d}")
        
        print(f"\n📊 合計テーブルサイズ: {total_size_bytes:,} バイト ({total_size_bytes / 1024 / 1024:.2f} MB)")
        
        # 接続数とアクティブなクエリを確認
        cursor.execute("""
            SELECT 
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active_connections,
                count(*) FILTER (WHERE state = 'idle') as idle_connections
            FROM pg_stat_activity 
            WHERE datname = current_database()
        """)
        
        conn_info = cursor.fetchone()
        total_conn, active_conn, idle_conn = conn_info
        
        print(f"\n🔗 接続状況:")
        print(f"  総接続数: {total_conn}")
        print(f"  アクティブ接続: {active_conn}")
        print(f"  アイドル接続: {idle_conn}")
        
        # 最近のアクティビティを確認
        cursor.execute("""
            SELECT 
                query_start,
                state,
                query
            FROM pg_stat_activity 
            WHERE datname = current_database() 
            AND state = 'active'
            ORDER BY query_start DESC
            LIMIT 5
        """)
        
        active_queries = cursor.fetchall()
        if active_queries:
            print(f"\n⚡ アクティブなクエリ（最新5件）:")
            for query in active_queries:
                start_time, state, query_text = query
                print(f"  {start_time}: {state} - {query_text[:100]}...")
        
        # AWS RDS無料枠の制限を確認
        print(f"\n⚠️ AWS RDS無料枠制限:")
        print(f"  ストレージ: 20GB")
        print(f"  現在使用量: {db_size_bytes / 1024 / 1024 / 1024:.2f}GB")
        print(f"  使用率: {(db_size_bytes / 1024 / 1024 / 1024) / 20 * 100:.1f}%")
        
        if db_size_bytes > 20 * 1024 * 1024 * 1024:  # 20GB
            print("❌ 無料枠のストレージ制限を超過しています！")
        else:
            print("✅ ストレージは無料枠内です")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_database_usage() 