import psycopg2
from contextlib import contextmanager
from flask import current_app

@contextmanager
def get_db_connection():
    """
    プール化された接続を取得（最適化版）
    """
    db_pool = getattr(current_app, 'db_pool', None)
    DB_HOST = current_app.config.get('DB_HOST')
    DB_PORT = current_app.config.get('DB_PORT')
    DB_NAME = current_app.config.get('DB_NAME')
    DB_USER = current_app.config.get('DB_USER')
    DB_PASSWORD = current_app.config.get('DB_PASSWORD')
    
    conn = None
    try:
        if db_pool:
            try:
                conn = db_pool.getconn()
            except Exception as e:
                current_app.logger.error(f"プールから接続取得エラー: {e}")
                conn = None
        if conn:
            conn.autocommit = False
            yield conn
        else:
            current_app.logger.warning("プール接続失敗、直接接続を試行")
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            yield conn
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        current_app.logger.error(f"DB接続エラー: {e}")
        raise
    finally:
        if conn and db_pool:
            try:
                db_pool.putconn(conn)
            except Exception as e:
                current_app.logger.error(f"DB接続返却エラー: {e}")
                if conn:
                    conn.close()
        elif conn:
            conn.close() 