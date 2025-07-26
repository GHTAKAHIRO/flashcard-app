import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from flask import current_app
import os

@contextmanager
def get_db_connection():
    """
    データベース接続を取得（SQLite/PostgreSQL対応版）
    """
    db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLite接続
        db_path = os.path.abspath(os.getenv('DB_PATH', 'flashcards.db'))
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能にする
            yield conn
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            current_app.logger.error(f"SQLite接続エラー: {e}")
            raise
        finally:
            if conn:
                conn.close()
    else:
        # PostgreSQL接続
        DB_HOST = current_app.config.get('DB_HOST')
        DB_PORT = current_app.config.get('DB_PORT')
        DB_NAME = current_app.config.get('DB_NAME')
        DB_USER = current_app.config.get('DB_USER')
        DB_PASSWORD = current_app.config.get('DB_PASSWORD')
        
        conn = None
        try:
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
            current_app.logger.error(f"PostgreSQL接続エラー: {e}")
            raise
        finally:
            if conn:
                conn.close() 

@contextmanager
def get_db_cursor(conn, cursor_factory=None):
    """
    データベースカーソルを取得（SQLite/PostgreSQL対応版）
    """
    db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLiteの場合は手動でカーソルを管理
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    else:
        # PostgreSQLの場合はコンテキストマネージャーを使用
        if cursor_factory:
            with conn.cursor(cursor_factory=cursor_factory) as cursor:
                yield cursor
        else:
            with conn.cursor() as cursor:
                yield cursor

def get_placeholder(db_type=None):
    """
    データベースタイプに応じたプレースホルダーを取得
    """
    if db_type is None:
        db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        return '?'
    else:
        return '%s' 