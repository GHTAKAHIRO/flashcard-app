import os
import psycopg2
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import sys
from tabulate import tabulate
from werkzeug.security import generate_password_hash

# 環境変数の読み込み
load_dotenv()

class RDSQueryExecutor:
    def __init__(self):
        self.conn_params = {
            'dbname': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT', '5432')
        }

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        クエリを実行し、結果を返します。
        
        Args:
            query (str): 実行するSQLクエリ
            params (tuple, optional): クエリパラメータ
            
        Returns:
            List[Dict[str, Any]]: クエリ結果のリスト
        """
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        results = [dict(zip(columns, row)) for row in cur.fetchall()]
                        return results
                    return []
        except Exception as e:
            print(f"Error executing query: {e}")
            raise

    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """
        更新クエリを実行し、影響を受けた行数を返します。
        
        Args:
            query (str): 実行するSQLクエリ
            params (tuple, optional): クエリパラメータ
            
        Returns:
            int: 影響を受けた行数
        """
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    conn.commit()
                    return cur.rowcount
        except Exception as e:
            print(f"Error executing update: {e}")
            raise

    def execute_transaction(self, queries: List[tuple]) -> bool:
        """
        複数のクエリをトランザクションとして実行します。
        
        Args:
            queries (List[tuple]): (クエリ, パラメータ)のタプルのリスト
            
        Returns:
            bool: トランザクションが成功したかどうか
        """
        try:
            with psycopg2.connect(**self.conn_params) as conn:
                with conn.cursor() as cur:
                    for query, params in queries:
                        cur.execute(query, params)
                    conn.commit()
                    return True
        except Exception as e:
            print(f"Error executing transaction: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("使用方法: python rds_query.py 'SQLクエリ'")
        sys.exit(1)

    query = sys.argv[1]
    executor = RDSQueryExecutor()

    try:
        if query.lower().startswith(('select', 'with')):
            results = executor.execute_query(query)
            if results:
                # 結果を表形式で表示
                headers = results[0].keys()
                rows = [list(row.values()) for row in results]
                print(tabulate(rows, headers=headers, tablefmt='grid'))
            else:
                print("クエリは実行されましたが、結果はありません。")
        else:
            affected_rows = executor.execute_update(query)
            print(f"クエリが実行されました。影響を受けた行数: {affected_rows}")
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

print(generate_password_hash('admin123')) 