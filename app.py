# ========== Redis除去版 パート1: 基本設定・インポート・初期化 ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import math
# PostgreSQL関連のインポートをコメントアウト（SQLite使用時）
# import psycopg2
# from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps
import json
import hashlib
import threading
import time
import queue
# import psycopg2.pool
from contextlib import contextmanager
import atexit
from flask_wtf.csrf import CSRFProtect
import io
import csv
import re
# import boto3  # AWS S3関連（現在は使用しない）
# from botocore.exceptions import ClientError  # AWS S3関連（現在は使用しない）
# from PIL import Image  # 画像処理（現在は使用しない）
import uuid
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.study import study_bp
from routes.vocabulary import vocabulary_bp
from models.user import User
from utils.db import get_db_connection, get_db_cursor

# ========== 設定エリア ==========
load_dotenv(dotenv_path='dbname.env')

# 環境変数の確認とログ出力
print("🔍 環境変数チェック:")
print(f"DB_TYPE: {os.getenv('DB_TYPE', 'sqlite')}")
print(f"DB_PATH: {os.getenv('DB_PATH', 'flashcards.db')}")
print(f"DB_HOST: {os.getenv('DB_HOST', 'Not set')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 'Not set')}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'Not set')}")
print(f"DB_USER: {os.getenv('DB_USER', 'Not set')}")
print(f"DB_PASSWORD: {'Set' if os.getenv('DB_PASSWORD') else 'Not set'}")
print(f"WASABI_ACCESS_KEY: {'Set' if os.getenv('WASABI_ACCESS_KEY') else 'Not set'}")
print(f"WASABI_SECRET_KEY: {'Set' if os.getenv('WASABI_SECRET_KEY') else 'Not set'}")
print(f"WASABI_BUCKET: {os.getenv('WASABI_BUCKET', 'Not set')}")
print(f"WASABI_ENDPOINT: {os.getenv('WASABI_ENDPOINT', 'Not set')}")

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
# csrf = CSRFProtect(app)  # 本番環境ではCSRF保護を無効化

# CSRFトークンを空文字列として提供（テンプレート互換性のため）
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=lambda: '')
logging.basicConfig(level=logging.DEBUG)

app.config.update(
    # JSON処理高速化
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=False,
    
    # セッション最適化
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    
    # 静的ファイルキャッシュ
    SEND_FILE_MAX_AGE_DEFAULT=31536000,  # 1年
    
    # データベース設定
    DB_TYPE=os.getenv('DB_TYPE', 'sqlite'),
    DB_PATH=os.getenv('DB_PATH', 'flashcards.db'),
    DB_HOST=os.getenv('DB_HOST'),
    DB_PORT=os.getenv('DB_PORT'),
    DB_NAME=os.getenv('DB_NAME'),
    DB_USER=os.getenv('DB_USER'),
    DB_PASSWORD=os.getenv('DB_PASSWORD')
)

print("🚀 バックエンド高速化システム初期化完了")

# Flask-Login 初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Blueprint登録
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(study_bp)
app.register_blueprint(vocabulary_bp)

# --- ここからカスタムフィルタ追加 ---
def to_kanji_circle(value):
    kanji_circles = {
        1: '①', 2: '②', 3: '③', 4: '④', 5: '⑤',
        6: '⑥', 7: '⑦', 8: '⑧', 9: '⑨', 10: '⑩'
    }
    try:
        return kanji_circles.get(int(value), str(value))
    except Exception:
        return str(value)

app.jinja_env.filters['to_kanji_circle'] = to_kanji_circle
# --- カスタムフィルタここまで ---

# 🚀 非同期ログ処理システム
log_queue = queue.Queue(maxsize=1000)
log_worker_active = True

def log_worker():
    """バックグラウンドでログを処理するワーカー"""
    while log_worker_active:
        try:
            log_data = log_queue.get(timeout=1)
            if log_data is None:  # 終了シグナル
                break
            
            user_id, card_id, result, stage, mode = log_data
            
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO study_log (user_id, card_id, result, stage, mode)
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (user_id, card_id, result, stage, mode))
                        conn.commit()
                app.logger.info(f"非同期ログ記録完了: user={user_id}, card={card_id}")
            except Exception as e:
                app.logger.error(f"非同期ログ書き込みエラー: {e}")
            finally:
                log_queue.task_done()
                
        except queue.Empty:
            continue
        except Exception as e:
            app.logger.error(f"ログワーカーエラー: {e}")

# ワーカースレッド開始
log_thread = threading.Thread(target=log_worker, daemon=True)
log_thread.start()

# Wasabi S3クライアント初期化
def init_wasabi_client():
    """Wasabi S3クライアントの初期化（現在は無効化）"""
    print("⚠️ Wasabi S3クライアントは現在無効化されています")
    return None

def get_unit_image_folder_path(question_id):
    """問題IDから単元の章番号に基づいて画像フォルダパスを生成"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 問題の単元情報を取得
                cur.execute('''
                    SELECT 
                        t.subject, 
                        t.wasabi_folder_path,
                        u.chapter_number
                    FROM social_studies_questions q
                    JOIN social_studies_units u ON q.unit_id = u.id
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
                    WHERE q.id = %s
                ''', (question_id,))
                result = cur.fetchone()
                
                if result:
                    subject, textbook_folder, chapter_number = result
                    
                    # 科目を英語に変換
                    subject_map = {
                        '地理': 'geography',
                        '歴史': 'history',
                        '公民': 'civics',
                        '理科': 'science'
                    }
                    subject_en = subject_map.get(subject, 'other')
                    
                    # 章番号が設定されている場合は章番号を使用、そうでなければデフォルト
                    if chapter_number:
                        folder_path = f"social_studies/{subject_en}/{chapter_number}"
                    else:
                        folder_path = f"social_studies/{subject_en}/default"
                    
                    print(f"🔍 生成されたフォルダパス: {folder_path}")
                    return folder_path
                else:
                    # 単元が設定されていない場合はデフォルトパス
                    print(f"⚠️ 問題ID {question_id} の単元情報が見つかりません")
                    return "social_studies/default"
                    
    except Exception as e:
        app.logger.error(f"フォルダパス生成エラー: {e}")
        return "social_studies/default"

def get_unit_image_folder_path_by_unit_id(unit_id):
    """単元IDから教材のWasabiフォルダパスと章番号に基づいて画像フォルダパスを生成"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 単元情報と教材のWasabiフォルダパスを取得
                cur.execute('''
                    SELECT 
                        t.subject, 
                        t.wasabi_folder_path,
                        u.chapter_number
                    FROM social_studies_units u
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = %s
                ''', (unit_id,))
                result = cur.fetchone()
                
                if result:
                    subject, wasabi_folder_path, chapter_number = result
                    
                    # 教材のWasabiフォルダパスが設定されている場合はそれを使用
                    if wasabi_folder_path:
                        if chapter_number:
                            folder_path = f"{wasabi_folder_path}/{chapter_number}"
                        else:
                            folder_path = f"{wasabi_folder_path}/default"
                    else:
                        # フォールバック: 科目を英語に変換
                        subject_map = {
                            '地理': 'geography',
                            '歴史': 'history',
                            '公民': 'civics',
                            '理科': 'science'
                        }
                        subject_en = subject_map.get(subject, 'other')
                        
                        if chapter_number:
                            folder_path = f"social_studies/{subject_en}/{chapter_number}"
                        else:
                            folder_path = f"social_studies/{subject_en}/default"
                    
                    print(f"🔍 単元ID {unit_id} から生成されたフォルダパス: {folder_path}")
                    return folder_path
                else:
                    # 単元が見つからない場合はデフォルトパス
                    print(f"⚠️ 単元ID {unit_id} が見つかりません")
                    return "social_studies/default"
                    
    except Exception as e:
        app.logger.error(f"フォルダパス生成エラー: {e}")
        return "social_studies/default"

# 画像アップロード関数
def upload_image_to_wasabi(image_file, question_id, textbook_id=None):
    """画像をWasabiにアップロード（現在は無効化）"""
    print("⚠️ 画像アップロード機能は現在無効化されています")
    return None, "画像アップロード機能は現在無効化されています"

def set_image_public_access(image_url):
    """既存の画像ファイルに公開アクセス権限を設定（現在は無効化）"""
    print("⚠️ 画像公開アクセス設定機能は現在無効化されています")
    return False, "画像公開アクセス設定機能は現在無効化されています"

# DB接続情報
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
db_pool = None

def init_connection_pool():
    """データベース接続プールの初期化（SQLite/PostgreSQL対応版）"""
    global db_pool
    db_type = os.environ.get('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLiteの場合はプールを使用しない
        db_pool = None
        app.logger.info("🚀 SQLiteデータベース接続初期化完了")
    else:
        # PostgreSQL接続プール
        try:
            # 本番環境では最小限の接続数に
            if os.environ.get('RENDER'):
                min_conn = 1
                max_conn = 3
            else:
                min_conn = 2
                max_conn = 10

            # PostgreSQL接続プール（現在は無効化）
            # db_pool = psycopg2.pool.SimpleConnectionPool(
            #     min_conn,
            #     max_conn,
            #     host=os.environ.get('DB_HOST'),
            #     port=os.environ.get('DB_PORT'),
            #     dbname=os.environ.get('DB_NAME'),
            #     user=os.environ.get('DB_USER'),
            #     password=os.environ.get('DB_PASSWORD')
            # )
            db_pool = None
            app.logger.info("🚀 PostgreSQLデータベース接続プール初期化完了")
        except Exception as e:
            app.logger.error(f"接続プール初期化エラー: {e}")
            raise

# 🔥 シンプルなインメモリキャッシュ（Redis代替）
memory_cache = {}
cache_timestamps = {}
cache_lock = threading.Lock()

print("📋 Redis除去版アプリ - 基本設定完了")

# ========== Redis除去版 パート2: データベース接続とインデックス最適化 ==========

def optimize_database_indexes():
    """🔥 データベースインデックス最適化（SQLite/PostgreSQL対応版）"""
    db_type = os.environ.get('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        # SQLite用インデックス
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_study_log_user_stage_mode ON study_log(user_id, stage, mode);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_composite ON study_log(user_id, stage, mode, card_id, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_page ON image(source, page_number);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_level ON image(source, level);",
            "CREATE INDEX IF NOT EXISTS idx_chunk_progress_user_source_stage ON chunk_progress(user_id, source, stage);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_card_result ON study_log(card_id, result, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_user_settings_user_source ON user_settings(user_id, source);"
        ]
    else:
        # PostgreSQL用インデックス
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_study_log_user_stage_mode ON study_log(user_id, stage, mode);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_composite ON study_log(user_id, stage, mode, card_id, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_page ON image(source, page_number);",
            "CREATE INDEX IF NOT EXISTS idx_image_source_level ON image(source, level);",
            "CREATE INDEX IF NOT EXISTS idx_chunk_progress_user_source_stage ON chunk_progress(user_id, source, stage);",
            "CREATE INDEX IF NOT EXISTS idx_study_log_card_result ON study_log(card_id, result, id DESC);",
            "CREATE INDEX IF NOT EXISTS idx_user_settings_user_source ON user_settings(user_id, source);"
        ]
    
    success_count = 0
    try:
        with get_db_connection() as conn:
            if db_type == 'sqlite':
                # SQLiteの場合はautocommitを設定しない
                pass
            else:
                conn.autocommit = True
            
            with conn.cursor() as cur:
                for index_sql in indexes:
                    try:
                        cur.execute(index_sql)
                        success_count += 1
                    except Exception as e:
                        if "already exists" not in str(e):
                            app.logger.error(f"インデックス作成エラー: {e}")
        
        app.logger.info(f"📊 データベース最適化完了: {success_count}個のインデックス")
    except Exception as e:
        app.logger.error(f"データベース最適化エラー: {e}")
        

# ========== Redis除去版 パート3: インメモリキャッシュシステム ==========

def cache_key(*args):
    """キャッシュキー生成"""
    key_string = "_".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

def simple_cache(expire_time=180):
    """シンプルキャッシュデコレータ（インメモリ）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}_{cache_key(*args, *kwargs.values())}"
            
            with cache_lock:
                # キャッシュチェック
                if key in memory_cache:
                    timestamp = cache_timestamps.get(key, 0)
                    if time.time() - timestamp < expire_time:
                        return memory_cache[key]
                    else:
                        # 期限切れキャッシュ削除
                        del memory_cache[key]
                        del cache_timestamps[key]
            
            # 関数実行
            result = func(*args, **kwargs)
            
            with cache_lock:
                # キャッシュ保存
                memory_cache[key] = result
                cache_timestamps[key] = time.time()
                
                # キャッシュサイズ制限（最大1000エントリ）
                if len(memory_cache) > 1000:
                    # 古いエントリを削除
                    oldest_key = min(cache_timestamps.keys(), key=lambda k: cache_timestamps[k])
                    del memory_cache[oldest_key]
                    del cache_timestamps[oldest_key]
            
            return result
        return wrapper
    return decorator

def clear_user_cache(user_id, source=None):
    """ユーザーキャッシュクリア"""
    with cache_lock:
        try:
            pattern = str(user_id)
            if source:
                pattern = f"{user_id}_{source}"
            
            keys_to_delete = []
            for key in memory_cache.keys():
                if pattern in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del memory_cache[key]
                if key in cache_timestamps:
                    del cache_timestamps[key]
            
            if keys_to_delete:
                app.logger.info(f"🗑️ キャッシュクリア: {len(keys_to_delete)}件")
        except Exception as e:
            app.logger.error(f"キャッシュクリアエラー: {e}")

# ========== Redis除去版 パート4: 基本ユーティリティ関数 ==========

def get_chunk_size_by_subject(subject):
    """科目別チャンクサイズを返す"""
    chunk_sizes = {
        '英語': 2,  # テスト用に小さく
        '数学': 2,  # テスト用に小さく
        '理科': 3,  # テスト用に小さく
        '社会': 3,  # テスト用に小さく
        '国語': 3   # テスト用に小さく
    }
    return chunk_sizes.get(subject, 2)

def create_chunks_for_cards(cards, subject):
    """カードリストをチャンクに分割"""
    chunk_size = get_chunk_size_by_subject(subject)
    chunks = []
    
    for i in range(0, len(cards), chunk_size):
        chunk = cards[i:i + chunk_size]
        chunks.append(chunk)
    
    return chunks

def parse_page_range(page_range_str):
    """ページ範囲文字列を解析"""
    pages = set()
    for part in page_range_str.split(','):
        if '-' in part:
            start, end = part.split('-')
            pages.update(str(i) for i in range(int(start), int(end) + 1))
        else:
            pages.add(part.strip())
    return list(pages)

# ========== User関連（Flask-Login用） ==========

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE id = ?", (user_id,))
                user = cur.fetchone()
                if user:
                    return User(*user)
    except Exception as e:
        app.logger.error(f"ユーザー読み込みエラー: {e}")
    return None

# ========== キャッシュバスター追加 ==========
@app.context_processor
def inject_timestamp():
    return {'timestamp': int(time.time())}
        

# ========== Redis除去版 パート5: 学習履歴チェック関数 ==========

@simple_cache(expire_time=300)
def has_study_history(user_id, source):
    """指定教材に学習履歴があるかチェック（キャッシュ付き）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT COUNT(*) FROM study_log sl
                    JOIN image i ON sl.card_id = i.id
                    WHERE sl.user_id = ? AND i.source = ?
                ''', (user_id, source))
                count = cur.fetchone()[0]
                return count > 0
    except Exception as e:
        app.logger.error(f"学習履歴チェックエラー: {e}")
        return False

@simple_cache(expire_time=120)
def check_chunk_completion(user_id, source, chapter_id, chunk_number):
    """指定チャンクが合格済みかチェック"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 最新のセッションで全問正解したかチェック
                cur.execute('''
                    SELECT vsl.session_id, COUNT(*) as total_words,
                           SUM(CASE WHEN vsl.result = 'known' THEN 1 ELSE 0 END) as correct_words
                    FROM vocabulary_study_log vsl
                    WHERE vsl.user_id = ? AND vsl.source = ? 
                    AND vsl.chapter_id = ? AND vsl.chunk_number = ?
                    GROUP BY vsl.session_id
                    ORDER BY vsl.study_date DESC
                    LIMIT 1
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                if result and result[1] > 0:
                    # 全問正解の場合のみ合格
                    return result[2] == result[1]
                return False
                
    except Exception as e:
        app.logger.error(f"チャンク合格判定エラー: {e}")
        return False

def get_vocabulary_chunk_progress(user_id, source, chapter_id, chunk_number):
    """英単語チャンクの進捗状況を取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 基本の進捗情報を取得
                cur.execute('''
                    SELECT is_completed, is_passed, completed_at, passed_at
                    FROM vocabulary_chunk_progress
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                # 正解数を取得
                cur.execute('''
                    SELECT COUNT(*) as correct_count
                    FROM vocabulary_study_log
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ? AND result = 'known'
                ''', (user_id, source, chapter_id, chunk_number))
                correct_result = cur.fetchone()
                correct_count = correct_result[0] if correct_result else 0
                
                if result:
                    result = dict(result)
                    result['correct_count'] = correct_count
                
                return result
    except Exception as e:
        app.logger.error(f"英単語チャンク進捗取得エラー: {e}")
        return None

def update_vocabulary_chunk_progress(user_id, source, chapter_id, chunk_number, is_completed=False, is_passed=False):
    """英単語チャンクの進捗状況を更新"""
    try:
        app.logger.info(f"進捗更新開始: user={user_id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, completed={is_completed}, passed={is_passed}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 既存のレコードがあるかチェック
                cur.execute('''
                    SELECT id FROM vocabulary_chunk_progress
                    WHERE user_id = %s AND source = %s AND chapter_id = %s AND chunk_number = %s
                ''', (user_id, source, chapter_id, chunk_number))
                
                existing = cur.fetchone()
                now = datetime.now()
                
                app.logger.info(f"既存レコード: {existing}")
                
                if existing:
                    # 既存レコードを更新
                    update_fields = []
                    params = []
                    
                    if is_completed:
                        update_fields.append("is_completed = TRUE")
                        update_fields.append("completed_at = %s")
                        params.append(now)
                    
                    if is_passed:
                        update_fields.append("is_passed = TRUE")
                        update_fields.append("passed_at = %s")
                        params.append(now)
                    
                    if update_fields:
                        update_fields.append("updated_at = %s")
                        params.append(now)
                        params.extend([user_id, source, chapter_id, chunk_number])
                        
                        update_sql = f'''
                            UPDATE vocabulary_chunk_progress
                            SET {', '.join(update_fields)}
                            WHERE user_id = %s AND source = %s AND chapter_id = %s AND chunk_number = %s
                        '''
                        app.logger.info(f"更新SQL: {update_sql}")
                        app.logger.info(f"更新パラメータ: {params}")
                        
                        cur.execute(update_sql, params)
                else:
                    # 新規レコードを作成
                    insert_sql = '''
                        INSERT INTO vocabulary_chunk_progress 
                        (user_id, source, chapter_id, chunk_number, is_completed, is_passed, completed_at, passed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    '''
                    insert_params = (
                        user_id, source, chapter_id, chunk_number,
                        is_completed, is_passed,
                        now if is_completed else None,
                        now if is_passed else None
                    )
                    app.logger.info(f"挿入SQL: {insert_sql}")
                    app.logger.info(f"挿入パラメータ: {insert_params}")
                    
                    cur.execute(insert_sql, insert_params)
                
                conn.commit()
                app.logger.info(f"進捗更新完了: 成功")
                return True
                
    except Exception as e:
        app.logger.error(f"英単語チャンク進捗更新エラー: {e}")
        app.logger.error(f"エラー詳細: {str(e)}")
        return False

def check_stage_completion(user_id, source, stage, page_range, difficulty):
    """指定ステージが完了しているかチェック（キャッシュ付き）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # ステージ1の場合、特別な条件を適用
                if stage == 1:
                    # まず、そのステージの全チャンク数を取得
                    cur.execute('''
                        SELECT total_chunks FROM chunk_progress 
                        WHERE user_id = %s AND source = %s AND stage = %s AND page_range = %s AND difficulty = %s
                        LIMIT 1
                    ''', (user_id, source, stage, page_range, difficulty))
                    result = cur.fetchone()
                    
                    if not result:
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}のチャンク情報が見つかりません")
                        return False
                    
                    total_chunks = result[0]
                    app.logger.debug(f"[STAGE_CHECK] Stage{stage}の全チャンク数: {total_chunks}")
                    
                    # 最後のチャンクのテスト結果を取得
                    cur.execute('''
                        SELECT cp.chunk_number, cp.test_completed, cp.practice_completed,
                               (SELECT result FROM study_log 
                                WHERE user_id = %s AND stage = 1 AND mode = 'test' 
                                AND card_id IN (
                                    SELECT card_id FROM image 
                                    WHERE user_id = %s AND source = %s AND stage = 1 
                                    AND page_range = %s AND difficulty = %s AND chunk_number = cp.chunk_number
                                )
                                ORDER BY id DESC LIMIT 1) as last_test_result
                        FROM chunk_progress cp
                        WHERE cp.user_id = %s AND cp.source = %s AND cp.stage = 1 
                        AND cp.page_range = %s AND cp.difficulty = %s
                        ORDER BY cp.chunk_number DESC
                        LIMIT 1
                    ''', (user_id, user_id, source, page_range, difficulty, user_id, source, page_range, difficulty))
                    last_chunk = cur.fetchone()
                    
                    if not last_chunk:
                        return False
                    
                    # 最後のチャンクのテストで全問正解の場合
                    if last_chunk[3] == 'known':
                        return True
                    
                    # 最後のチャンクのテストで間違えた問題があり、練習で全問正解になった場合
                    if last_chunk[1] and last_chunk[2]:
                        return True
                    
                    return False
                
                # ステージ2・3の場合、Universal進捗管理を使用
                elif stage in [2, 3]:
                    chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
                    if chunk_progress and chunk_progress.get('all_completed'):
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}完了済み (Universal進捗)")
                        return True
                    else:
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}未完了 (Universal進捗)")
                        return False
                
                # その他のステージは従来の条件を適用
                else:
                    # まず、そのステージの全チャンク数を取得
                    cur.execute('''
                        SELECT total_chunks FROM chunk_progress 
                        WHERE user_id = %s AND source = %s AND stage = %s AND page_range = %s AND difficulty = %s
                        LIMIT 1
                    ''', (user_id, source, stage, page_range, difficulty))
                    result = cur.fetchone()
                    
                    if not result:
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}のチャンク情報が見つかりません")
                        return False
                    
                    total_chunks = result[0]
                    app.logger.debug(f"[STAGE_CHECK] Stage{stage}の全チャンク数: {total_chunks}")
                    
                    cur.execute('''
                        SELECT COUNT(*) FROM chunk_progress 
                                    WHERE user_id = %s AND source = %s AND stage = %s 
                        AND page_range = %s AND difficulty = %s 
                        AND test_completed = true 
                        AND (practice_completed = true OR practice_needed = false)
                    ''', (user_id, source, stage, page_range, difficulty))
                    completed_chunks = cur.fetchone()[0]
                    
                    is_completed = completed_chunks == total_chunks
                    
                    if is_completed:
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}完了済み ({completed_chunks}/{total_chunks}チャンク)")
                    else:
                        app.logger.debug(f"[STAGE_CHECK] Stage{stage}未完了 ({completed_chunks}/{total_chunks}チャンク)")
                    
                    return is_completed
                    
    except Exception as e:
        app.logger.error(f"[STAGE_CHECK] Stage{stage}チェックエラー: {e}")
        return False

def get_completed_stages_chunk_aware(user_id, source, page_range, difficulty=''):
    """チャンク完了を考慮した完了ステージ取得"""
    result = {'test': set(), 'practice': set(), 'perfect_completion': False, 'practice_history': {}}
    user_id = str(user_id)

    try:
        # ステージ1の完了判定（チャンクベース）
        chunk_progress = get_or_create_chunk_progress(user_id, source, 1, page_range, difficulty)
        
        if chunk_progress and chunk_progress.get('all_completed'):
            result['test'].add(1)
            result['practice'].add(1)
            
            # 以降のステージ判定は簡略化
        
        # 練習履歴の設定
        for stage in [1, 2, 3]:
            result['practice_history'][stage] = stage in result['practice']
                
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result

# ========== Redis除去版 パート6: カード取得関数群 ==========

@simple_cache(expire_time=60)
def get_study_cards_fast(source, stage, mode, page_range, user_id, difficulty='', chunk_number=None):
    """超高速化されたカード取得"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 最適化されたクエリ
                base_query = '''
                    SELECT id, subject, page_number, problem_number, level, image_problem, image_answer
                    FROM image
                    WHERE source = %s
                '''
                params = [source]

                # ページ範囲処理（最適化）
                if page_range:
                    page_list = []
                    for part in page_range.split(','):
                        part = part.strip()
                        if '-' in part and part.count('-') == 1:
                            try:
                                start, end = map(int, part.split('-'))
                                page_list.extend(str(i) for i in range(start, min(end + 1, start + 100)))
                            except ValueError:
                                page_list.append(part)
                        else:
                            page_list.append(part)
                    
                    if page_list:
                        placeholders = ','.join(['%s'] * len(page_list))
                        base_query += f' AND page_number IN ({placeholders})'
                        params.extend(page_list)

                # 難易度フィルタ
                if difficulty:
                    difficulty_list = [d.strip() for d in difficulty.split(',')]
                    placeholders = ','.join(['%s'] * len(difficulty_list))
                    base_query += f' AND level IN ({placeholders})'
                    params.extend(difficulty_list)

                # ステージ別フィルタ
                if stage == 2:
                    base_query += '''
                        AND id IN (
                            SELECT DISTINCT card_id FROM study_log
                            WHERE user_id = %s AND stage = 1 AND mode = 'test' AND result = 'unknown'
                        )
                    '''
                    params.append(user_id)
                elif stage == 3:
                    base_query += '''
                        AND id IN (
                            SELECT DISTINCT card_id FROM study_log
                            WHERE user_id = %s AND stage = 2 AND mode = 'test' AND result = 'unknown'
                        )
                    '''
                    params.append(user_id)

                base_query += ' ORDER BY id LIMIT 1000'
                
                cur.execute(base_query, params)
                records = cur.fetchall()

                # 辞書化
                cards = [
                    {
                        'id': r[0], 'subject': r[1], 'page_number': r[2],
                        'problem_number': r[3], 'level': r[4],
                        'image_problem': r[5], 'image_answer': r[6],
                        'grade': '', 'source': source, 'topic': '', 'format': ''
                    }
                    for r in records
                ]

                # Stage 1のチャンク分割
                if stage == 1 and chunk_number and cards:
                    chunk_size = get_chunk_size_by_subject(cards[0]['subject'])
                    start_idx = (chunk_number - 1) * chunk_size
                    end_idx = start_idx + chunk_size
                    return cards[start_idx:end_idx]

                return cards

    except Exception as e:
        app.logger.error(f"高速カード取得エラー: {e}")
        return []

def preload_next_chunk_data(user_id, source, stage, page_range, difficulty, current_chunk):
    """次のチャンクデータを非同期でプリロード"""
    try:
        next_chunk = current_chunk + 1
        threading.Thread(
            target=lambda: get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, next_chunk),
            daemon=True
        ).start()
    except Exception as e:
        app.logger.debug(f"プリロードエラー: {e}")

@simple_cache(expire_time=120)
def get_stage2_cards(source, page_range, user_id, difficulty):
    """Stage 2: Stage 1の×問題を全て取得（キャッシュ付き）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE source = %s
                '''
                params = [source]

                # ページ範囲の処理
                page_conditions = []
                if page_range:
                    for part in page_range.split(','):
                        part = part.strip()
                        if '-' in part:
                            try:
                                start, end = map(int, part.split('-'))
                                page_conditions.extend([str(i) for i in range(start, end + 1)])
                            except ValueError:
                                pass
                        else:
                            page_conditions.append(part)

                if page_conditions:
                    placeholders = ','.join(['%s'] * len(page_conditions))
                    query += f' AND page_number IN ({placeholders})'
                    params.extend(page_conditions)
                else:
                    query += ' AND false'

                # 難易度フィルタ
                if difficulty:
                    difficulty_list = [d.strip() for d in difficulty.split(',')]
                    difficulty_placeholders = ','.join(['%s'] * len(difficulty_list))
                    query += f' AND level IN ({difficulty_placeholders})'
                    params.extend(difficulty_list)

                # Stage 1の×問題のみ
                query += '''
                    AND id IN (
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = 1 AND mode = 'test'
                        ) AS ranked
                        WHERE rn = 1 AND result = 'unknown'
                    )
                '''
                params.append(user_id)

                query += ' ORDER BY id'
                cur.execute(query, params)
                records = cur.fetchall()

                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
    except Exception as e:
        app.logger.error(f"Stage 2カード取得エラー: {e}")
        return []

@simple_cache(expire_time=120)
def get_stage3_cards(source, page_range, user_id, difficulty):
    """Stage 3: Stage 2の×問題を全て取得（キャッシュ付き）"""
    try:
        # ステージ2の完了チェックを追加
        stage2_completed = check_stage_completion(user_id, source, 2, page_range, difficulty)
        if not stage2_completed:
            app.logger.debug(f"[STAGE3_CARDS] Stage2未完了のためStage3カードは取得しない")
            return []
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE source = %s
                '''
                params = [source]

                # ページ範囲の処理（Stage 2と同じ）
                page_conditions = []
                if page_range:
                    for part in page_range.split(','):
                        part = part.strip()
                        if '-' in part:
                            try:
                                start, end = map(int, part.split('-'))
                                page_conditions.extend([str(i) for i in range(start, end + 1)])
                            except ValueError:
                                pass
                        else:
                            page_conditions.append(part)

                if page_conditions:
                    placeholders = ','.join(['%s'] * len(page_conditions))
                    query += f' AND page_number IN ({placeholders})'
                    params.extend(page_conditions)
                else:
                    query += ' AND false'

                # 難易度フィルタ
                if difficulty:
                    difficulty_list = [d.strip() for d in difficulty.split(',')]
                    difficulty_placeholders = ','.join(['%s'] * len(difficulty_list))
                    query += f' AND level IN ({difficulty_placeholders})'
                    params.extend(difficulty_list)

                # Stage 2の×問題のみ
                query += '''
                    AND id IN (
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = 2 AND mode = 'test'
                        ) AS ranked
                        WHERE rn = 1 AND result = 'unknown'
                    )
                '''
                params.append(user_id)

                query += ' ORDER BY id'
                cur.execute(query, params)
                records = cur.fetchall()

                app.logger.debug(f"[STAGE3_CARDS] {len(records)}件のカードを取得")
                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
    except Exception as e:
        app.logger.error(f"Stage 3カード取得エラー: {e}")
        return []
    
# ========== Redis除去版 パート7: チャンク進捗管理関数群 ==========

def get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty):
    """Stage 1用のチャンク進捗を取得または作成（最適化版）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT chunk_number, total_chunks, completed 
                    FROM chunk_progress 
                    WHERE user_id = %s AND source = %s AND stage = %s
                    ORDER BY chunk_number
                ''', (user_id, source, stage))
                existing_chunks = cur.fetchall()
                
                if existing_chunks:
                    total_chunks = existing_chunks[0][1]
                    completed_chunks_before = [chunk[0] for chunk in existing_chunks if chunk[2]]
                    
                    # 各チャンクの完了状況をチェック・更新
                    for chunk_num in range(1, total_chunks + 1):
                        image = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        
                        if image:
                            chunk_card_ids = [card['id'] for card in image]
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id)
                                FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = %s AND card_id = ANY(%s)
                            ''', (user_id, stage, 'test', chunk_card_ids))
                            completed_count = cur.fetchone()[0]
                            
                            if completed_count == len(chunk_card_ids):
                                cur.execute('''
                                    UPDATE chunk_progress 
                                    SET completed = true, completed_at = CURRENT_TIMESTAMP
                                    WHERE user_id = %s AND source = %s AND stage = %s AND chunk_number = %s AND completed = false
                                ''', (user_id, source, stage, chunk_num))
                    
                    conn.commit()
                    
                    # 完了済みチャンクを再取得
                    cur.execute('''
                        SELECT chunk_number FROM chunk_progress 
                        WHERE user_id = %s AND source = %s AND stage = %s AND completed = true
                        ORDER BY chunk_number
                    ''', (user_id, source, stage))
                    completed_chunks_after = [row[0] for row in cur.fetchall()]
                    
                    newly_completed = set(completed_chunks_after) - set(completed_chunks_before)
                    
                    if len(completed_chunks_after) < total_chunks:
                        next_chunk = len(completed_chunks_after) + 1
                        result = {
                            'current_chunk': next_chunk,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after
                        }
                        
                        if newly_completed:
                            result['newly_completed_chunk'] = max(newly_completed)
                            result['needs_immediate_practice'] = True
                        
                        return result
                    else:
                        result = {
                            'current_chunk': None,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after,
                            'all_completed': True
                        }
                        
                        if newly_completed:
                            result['newly_completed_chunk'] = max(newly_completed)
                            result['needs_immediate_practice'] = True
                        
                        return result
                else:
                    # 新規作成
                    cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty)
                    
                    if not cards:
                        return None
                    
                    subject = cards[0]['subject']
                    chunk_size = get_chunk_size_by_subject(subject)
                    total_chunks = math.ceil(len(cards) / chunk_size)
                    
                    for chunk_num in range(1, total_chunks + 1):
                        cur.execute('''
                            INSERT INTO chunk_progress (user_id, source, stage, chunk_number, total_chunks, page_range, difficulty)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, source, stage, chunk_number) DO NOTHING
                        ''', (user_id, source, stage, chunk_num, total_chunks, page_range, difficulty))
                    
                    conn.commit()
                    
                    return {
                        'current_chunk': 1,
                        'total_chunks': total_chunks,
                        'completed_chunks': []
                    }
                    
    except Exception as e:
        app.logger.error(f"チャンク進捗取得エラー: {e}")
        return None

def get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty):
    """Stage 2・3用のチャンク進捗管理（エラーハンドリング強化版）"""
    try:
        app.logger.debug(f"[Universal進捗] Stage{stage}開始: user_id={user_id}")
        
        # Stage 2・3は統合復習なので1チャンクとして扱う
        if stage == 2:
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            return get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
        
        # Stage 3の前提条件チェック
        if stage == 3:
            stage2_completed = check_stage_completion(user_id, source, 2, page_range, difficulty)
            if not stage2_completed:
                app.logger.warning(f"[Universal進捗] Stage2未完了のためStage3はアクセス不可")
                return None
        
        if not target_cards:
            app.logger.debug(f"[Universal進捗] Stage{stage}: 対象カードなし")
            return {
                'current_chunk': None,
                'total_chunks': 1,
                'completed_chunks': [1],
                'all_completed': True,
                'no_target_cards': True
            }
        
        total_chunks = 1
        chunk_number = 1
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 既存の進捗をチェック
                cur.execute('''
                    SELECT chunk_number, total_chunks, completed 
                    FROM chunk_progress 
                    WHERE user_id = %s AND source = %s AND stage = %s
                    ORDER BY chunk_number
                ''', (user_id, source, stage))
                existing_chunks = cur.fetchall()
                
                if not existing_chunks:
                    cur.execute('''
                        INSERT INTO chunk_progress (user_id, source, stage, chunk_number, total_chunks, page_range, difficulty)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, source, stage, chunk_number) DO NOTHING
                    ''', (user_id, source, stage, chunk_number, total_chunks, page_range, difficulty))
                    conn.commit()
                
                # テスト完了チェック
                target_card_ids = [card['id'] for card in target_cards]
                cur.execute('''
                    SELECT COUNT(DISTINCT card_id)
                    FROM study_log
                    WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                ''', (user_id, stage, target_card_ids))
                tested_count = cur.fetchone()[0]
                
                is_test_completed = tested_count == len(target_card_ids)
                
                # 練習完了チェック
                practice_mode = 'practice'
                cur.execute('''
                    SELECT card_id FROM (
                        SELECT card_id, result,
                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test'
                        AND card_id = ANY(%s)
                    ) AS test_ranked
                    WHERE rn = 1 AND result = 'unknown'
                ''', (user_id, stage, target_card_ids))
                test_wrong_card_ids = [row[0] for row in cur.fetchall()]
                
                is_practice_completed = True
                if test_wrong_card_ids:
                    cur.execute('''
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = %s
                            AND card_id = ANY(%s)
                        ) AS practice_ranked
                        WHERE rn = 1 AND result = 'known'
                    ''', (user_id, stage, practice_mode, test_wrong_card_ids))
                    practice_correct_card_ids = [row[0] for row in cur.fetchall()]
                    is_practice_completed = len(practice_correct_card_ids) == len(test_wrong_card_ids)
                
                all_completed = is_test_completed and is_practice_completed
                
                if all_completed:
                    cur.execute('''
                        UPDATE chunk_progress 
                        SET completed = true, completed_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND source = %s AND stage = %s AND chunk_number = %s AND completed = false
                    ''', (user_id, source, stage, chunk_number))
                    conn.commit()
                
                result = {
                    'current_chunk': None if all_completed else chunk_number,
                    'total_chunks': total_chunks,
                    'completed_chunks': [chunk_number] if all_completed else [],
                    'all_completed': all_completed,
                    'needs_immediate_practice': False
                }
                
                app.logger.debug(f"[Universal進捗] Stage{stage}完了: {result}")
                return result
                
    except Exception as e:
        app.logger.error(f"[Universal進捗] Stage{stage}エラー: {e}")
        import traceback
        app.logger.error(f"[Universal進捗] トレースバック: {traceback.format_exc()}")
        return None

# ========== Redis除去版 パート8: 練習問題取得関数群 ==========

def get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty):
    """Stage 1用の指定チャンクの練習問題を取得（最適化版）"""
    try:
        image = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
        
        if not image:
            return []
        
        chunk_card_ids = [card['id'] for card in image]
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # テスト時に×だった問題を取得
                cur.execute('''
                    SELECT card_id FROM (
                        SELECT card_id, result,
                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test'
                        AND card_id = ANY(%s)
                    ) AS test_ranked
                    WHERE rn = 1 AND result = 'unknown'
                ''', (user_id, stage, chunk_card_ids))
                
                wrong_card_ids = [row[0] for row in cur.fetchall()]
                
                if not wrong_card_ids:
                    return []
                
                # 練習で○になった問題を除外
                cur.execute('''
                    SELECT card_id FROM (
                        SELECT card_id, result,
                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'chunk_practice'
                        AND card_id = ANY(%s)
                    ) AS practice_ranked
                    WHERE rn = 1 AND result = 'known'
                ''', (user_id, stage, wrong_card_ids))
                
                practiced_correct_ids = [row[0] for row in cur.fetchall()]
                need_practice_ids = [cid for cid in wrong_card_ids if cid not in practiced_correct_ids]
                
                if not need_practice_ids:
                    return []
                
                # 練習対象のカード詳細を取得
                cur.execute('''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE id = ANY(%s)
                    ORDER BY id
                ''', (need_practice_ids,))
                
                records = cur.fetchall()
                
                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
        
    except Exception as e:
        app.logger.error(f"練習問題取得エラー: {e}")
        return []

def get_chunk_practice_cards_universal(user_id, source, stage, chunk_number, page_range, difficulty):
    """Stage 2・3対応のチャンク練習問題取得（最適化版）"""
    try:
        if stage == 2:
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            return get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty)
        
        if not target_cards:
            return []
        
        target_card_ids = [card['id'] for card in target_cards]
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                practice_mode = 'practice'
                
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE id = ANY(%s)
                    AND id IN (
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'test'
                            AND card_id = ANY(%s)
                        ) AS test_ranked
                        WHERE rn = 1 AND result = 'unknown'
                    )
                    AND id NOT IN (
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = %s
                            AND card_id = ANY(%s)
                        ) AS practice_ranked
                        WHERE rn = 1 AND result = 'known'
                    )
                    ORDER BY id
                '''
                
                cur.execute(query, (
                    target_card_ids,
                    user_id, stage, target_card_ids,
                    user_id, stage, practice_mode, target_card_ids
                ))
                
                records = cur.fetchall()
                
                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
        
    except Exception as e:
        app.logger.error(f"練習問題取得エラー: {e}")
        return []

def is_stage_perfect(user_id, source, stage, page_range, difficulty):
    """指定ステージが全問正解か判定（testの最新結果が全てknownの場合のみTrue）"""
    cards = []
    if stage == 1:
        cards = get_study_cards_fast(source, 1, 'test', page_range, user_id, difficulty)
    elif stage == 2:
        cards = get_stage2_cards(source, page_range, user_id, difficulty)
    elif stage == 3:
        cards = get_stage3_cards(source, page_range, user_id, difficulty)
    if not cards:
        return False
    card_ids = [card['id'] for card in cards]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT card_id, result
                FROM (
                    SELECT card_id, result,
                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                    FROM study_log
                    WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                ) AS ranked
                WHERE rn = 1
            ''', (user_id, stage, card_ids))
            latest_results = dict(cur.fetchall())
    return all(latest_results.get(cid) == 'known' for cid in card_ids)

def get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty):
    """全ステージの詳細進捗情報を取得（全問正解なら次ステージを表示しない）"""
    stages_info = []
    try:
        # ステージ1
        stage1_info = get_stage_detailed_progress(user_id, source, 1, page_range, difficulty)
        if stage1_info:
            stages_info.append(stage1_info)
            if is_stage_perfect(user_id, source, 1, page_range, difficulty):
                return stages_info
        # ステージ2
        stage2_info = get_stage_detailed_progress(user_id, source, 2, page_range, difficulty)
        if stage2_info:
            stages_info.append(stage2_info)
            if is_stage_perfect(user_id, source, 2, page_range, difficulty):
                return stages_info
        # ステージ3
        stage3_info = get_stage_detailed_progress(user_id, source, 3, page_range, difficulty)
        if stage3_info:
            stages_info.append(stage3_info)
        return stages_info
    except Exception as e:
        app.logger.error(f"詳細進捗エラー: {e}")
        return []

def create_fallback_stage_info(source, page_range, difficulty, user_id):
    """エラー時のフォールバック：最小限のStage 1情報"""
    try:
        cards = get_study_cards_fast(source, 1, 'test', page_range, user_id, difficulty)
        
        if cards:
            subject = cards[0]['subject']
            chunk_size = get_chunk_size_by_subject(subject)
            total_chunks = math.ceil(len(cards) / chunk_size)
        else:
            total_chunks = 1
        
        return [{
            'stage': 1,
            'stage_name': 'ステージ 1',
            'total_cards': len(cards) if cards else 0,
            'total_chunks': total_chunks,
            'chunks_progress': [{
                'chunk_number': 1,
                'total_cards': chunk_size if cards else 0,
                'test_completed': False,
                'test_correct': 0,
                'test_wrong': 0,
                'practice_needed': False,
                'practice_completed': False,
                'chunk_completed': False,
                'can_start_test': True,
                'can_start_practice': False
            }],
            'stage_completed': False,
            'can_start': True
        }]
        
    except Exception as e:
        app.logger.error(f"フォールバック エラー: {e}")
        return []

# ========== Redis除去版 パート9: ステージ詳細進捗関数 ==========

def get_stage_detailed_progress(user_id, source, stage, page_range, difficulty):
    """指定ステージの詳細進捗を取得（練習表示改善版）"""
    try:
        # Stage 2の前提条件チェック
        if stage == 2:
            stage1_completed = check_stage_completion(user_id, source, 1, page_range, difficulty)
            if not stage1_completed:
                app.logger.warning(f"[STAGE_PROGRESS] Stage1未完了のためStage2は表示しない")
                return None
        
        # Stage 3の前提条件チェック
        if stage == 3:
            stage2_completed = check_stage_completion(user_id, source, 2, page_range, difficulty)
            if not stage2_completed:
                app.logger.warning(f"[STAGE_PROGRESS] Stage2未完了のためStage3は表示しない")
                return None
        
        # ステージ別の対象カードを取得
        if stage == 1:
            target_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty)
        elif stage == 2:
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            target_cards = []
        
        if not target_cards:
            app.logger.debug(f"[STAGE_PROGRESS] Stage{stage}: 対象カードなし")
            return None
        
        subject = target_cards[0]['subject']
        
        # ステージ2・3の場合はUniversal進捗管理を使用
        if stage in [2, 3]:
            chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
            if not chunk_progress:
                app.logger.debug(f"[STAGE_PROGRESS] Stage{stage}: Universal進捗取得失敗")
                return None
            
            # ステージ2・3は1チャンクとして扱う
            chunks = [target_cards]
            total_chunks = 1
            stage_completed = chunk_progress.get('all_completed', False)
            
        else:
            # ステージ1の場合は従来の処理
            chunks = create_chunks_for_cards(target_cards, subject)
            total_chunks = len(chunks)
            stage_completed = True
        
        # 各チャンクの進捗を取得
        chunks_progress = []
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for chunk_num in range(1, total_chunks + 1):
                    if stage == 1:
                        image = chunks[chunk_num - 1]
                    else:
                        image = target_cards
                    
                    chunk_card_ids = [card['id'] for card in image]
                    
                    # テスト進捗
                    cur.execute('''
                        SELECT card_id, result FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'test'
                            AND card_id = ANY(%s)
                        ) AS ranked
                        WHERE rn = 1
                    ''', (user_id, stage, chunk_card_ids))
                    test_results = dict(cur.fetchall())
                    
                    # 練習進捗
                    practice_mode = 'chunk_practice' if stage == 1 else 'practice'
                    cur.execute('''
                        SELECT card_id, result FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = %s
                            AND card_id = ANY(%s)
                        ) AS ranked
                        WHERE rn = 1
                    ''', (user_id, stage, practice_mode, chunk_card_ids))
                    practice_results = dict(cur.fetchall())
                    
                    # チャンク状態を判定
                    test_completed = len(test_results) == len(chunk_card_ids)
                    test_wrong_cards = [cid for cid, result in test_results.items() if result == 'unknown']
                    
                    # 🚀 練習状況の詳細チェック（シンプル化）
                    practice_completed = True
                    remaining_practice_cards = 0
                    
                    if test_wrong_cards:
                        practice_correct_cards = [cid for cid, result in practice_results.items() if result == 'known']
                        remaining_wrong_cards = [cid for cid in test_wrong_cards if cid not in practice_correct_cards]
                        remaining_practice_cards = len(remaining_wrong_cards)
                        practice_completed = remaining_practice_cards == 0
                    
                    # チャンク完了判定を厳密化：テスト完了かつ練習完了の場合のみTrue
                    chunk_completed = test_completed and practice_completed
                    
                    if not chunk_completed:
                        stage_completed = False
                    
                    # チャンク開始可能判定
                    if chunk_num == 1:
                        can_start_test = True
                    else:
                        can_start_test = chunks_progress[chunk_num-2]['chunk_completed']
                    
                    chunk_progress = {
                        'chunk_number': chunk_num,
                        'total_cards': len(chunk_card_ids),
                        'test_completed': test_completed,
                        'test_correct': len([r for r in test_results.values() if r == 'known']),
                        'test_wrong': len(test_wrong_cards),
                        'practice_needed': len(test_wrong_cards) > 0,
                        'practice_completed': practice_completed,
                        'remaining_practice_cards': remaining_practice_cards,  # 🚀 残り練習カード数を追加
                        'chunk_completed': chunk_completed,
                        'can_start_test': can_start_test,
                        'can_start_practice': test_completed and remaining_practice_cards > 0  # 🚀 練習可能判定を改善
                    }
                    
                    chunks_progress.append(chunk_progress)
        
        # Stage 3では前のステージ完了が必要
        can_start = True
        if stage == 2:
            can_start = check_stage_completion(user_id, source, 1, page_range, difficulty)
        elif stage == 3:
            can_start = check_stage_completion(user_id, source, 2, page_range, difficulty)
        
        stage_info = {
            'stage': stage,
            'stage_name': f'ステージ {stage}',
            'total_cards': len(target_cards),
            'total_chunks': total_chunks,
            'chunks_progress': chunks_progress,
            'stage_completed': stage_completed,
            'can_start': can_start
        }
        
        return stage_info
        
    except Exception as e:
        app.logger.error(f"[STAGE_PROGRESS] Stage{stage}進捗エラー: {e}")
        import traceback
        app.logger.error(f"[STAGE_PROGRESS] トレースバック: {traceback.format_exc()}")
        return None

# ========== 認証ルート ==========
# 認証関連のルートは routes/auth.py に移動済み

@app.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        # 管理者の場合は管理者画面にリダイレクト
        if current_user.is_admin:
            return redirect(url_for('admin.admin'))
        return redirect(url_for('admin.admin'))
    return redirect(url_for('auth.login'))

# favicon.icoのルートを追加
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

# 学習関連のルートは routes/study.py に移動済み

# 学習関連のルートは routes/study.py に移動済み

# 学習関連のルートは routes/study.py に移動済み

# 学習関連のルートは routes/study.py に移動済み

def is_all_stages_perfect(user_id, source, page_range, difficulty):
    return (
        is_stage_perfect(user_id, source, 1, page_range, difficulty) and
        is_stage_perfect(user_id, source, 2, page_range, difficulty) and
        is_stage_perfect(user_id, source, 3, page_range, difficulty)
    )

# 学習関連のルートは routes/study.py に移動済み

# ========== Redis除去版 パート12: 学習実行ルート ==========

# 学習関連のルートは routes/study.py に移動済み

# ========== 社会科一問一答機能 ==========



# ========== 社会科一問一答機能 ==========

def normalize_answer(answer):
    """回答を正規化（空白除去、全角→半角変換など）"""
    if not answer:
        return ""
    
    # 空白を除去（日本語の場合は小文字化しない）
    normalized = re.sub(r'\s+', '', answer)
    
    # 全角数字を半角に変換
    normalized = normalized.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    
    # 全角英字を半角に変換
    fullwidth_chars = 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    halfwidth_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    normalized = normalized.translate(str.maketrans(fullwidth_chars, halfwidth_chars))
    
    # 全角記号を半角に変換
    fullwidth_symbols = '！＠＃＄％＾＆＊（）＿＋－＝｛｝｜：；＂＇＜＞？、。・～'
    halfwidth_symbols = '!@#$%^&*()_+-={}|:;"\'<>?,./~'
    normalized = normalized.translate(str.maketrans(fullwidth_symbols, halfwidth_symbols))
    
    # 全角スペースを半角スペースに変換
    normalized = normalized.replace('　', ' ')
    
    # 連続するスペースを単一のスペースに変換
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # 前後のスペースを除去
    normalized = normalized.strip()
    
    return normalized

def check_answer(user_answer, correct_answer, acceptable_answers=None):
    """回答をチェックする"""
    user_norm = normalize_answer(user_answer)
    correct_norm = normalize_answer(correct_answer)
    
    app.logger.info(f"採点: ユーザー回答='{user_answer}' -> 正規化='{user_norm}', 正解='{correct_answer}' -> 正規化='{correct_norm}'")
    
    # 完全一致
    if user_norm == correct_norm:
        app.logger.info("完全一致で正解")
        return True, "完全一致"
    
    # 許容回答のチェック
    if acceptable_answers:
        app.logger.info(f"許容回答チェック: {acceptable_answers}")
        for acceptable in acceptable_answers:
            acceptable_norm = normalize_answer(acceptable)
            app.logger.info(f"許容回答比較: '{acceptable}' -> '{acceptable_norm}' vs '{user_norm}'")
            if user_norm == acceptable_norm:
                app.logger.info("許容回答で正解")
                return True, "許容回答"
    
    # 数字のみの場合は数値として比較
    if user_norm.isdigit() and correct_norm.isdigit():
        if int(user_norm) == int(correct_norm):
            return True, "数値一致"
    
    # 部分一致（キーワードチェック）
    correct_words = set(correct_norm.split())
    user_words = set(user_norm.split())
    
    if len(correct_words) > 0:
        match_ratio = len(correct_words.intersection(user_words)) / len(correct_words)
        if match_ratio >= 0.7:  # 70%以上のキーワードが一致
            return True, f"部分一致 ({match_ratio:.1%})"
    
    # 文字列の類似度チェック（編集距離ベース）
    if len(correct_norm) > 0:
        similarity = calculate_similarity(user_norm, correct_norm)
        if similarity >= 0.8:  # 80%以上の類似度
            return True, f"類似一致 ({similarity:.1%})"
    
    return False, "不正解"

def calculate_similarity(str1, str2):
    """文字列の類似度を計算（編集距離ベース）"""
    if not str1 or not str2:
        return 0.0
    
    # 短い方の文字列を基準にする
    if len(str1) > len(str2):
        str1, str2 = str2, str1
    
    # 編集距離を計算
    distance = levenshtein_distance(str1, str2)
    max_len = max(len(str1), len(str2))
    
    if max_len == 0:
        return 1.0
    
    return 1.0 - (distance / max_len)

def levenshtein_distance(str1, str2):
    """レーベンシュタイン距離を計算"""
    if len(str1) < len(str2):
        return levenshtein_distance(str2, str1)
    
    if len(str2) == 0:
        return len(str1)
    
    previous_row = list(range(len(str2) + 1))
    for i, c1 in enumerate(str1):
        current_row = [i + 1]
        for j, c2 in enumerate(str2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]



@app.route('/social_studies/quiz/<subject>')
@login_required
def social_studies_quiz(subject):
    """社会科クイズ画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 指定された科目の問題を取得
                cur.execute('''
                    SELECT id, question, correct_answer, acceptable_answers, answer_suffix, explanation, image_url
                    FROM social_studies_questions 
                    WHERE subject = ? 
                    ORDER BY RANDOM() 
                    LIMIT 10
                ''', (subject,))
                questions = cur.fetchall()
                
                if not questions:
                    flash('この科目の問題が見つかりません', 'error')
                    return redirect(url_for('admin.admin'))
                
                return render_template('social_studies/quiz.html', 
                                     questions=questions, 
                                     subject=subject)
    except Exception as e:
        app.logger.error(f"社会科クイズ画面エラー: {e}")
        flash('問題の取得に失敗しました', 'error')
        return redirect(url_for('admin.admin'))

@app.route('/social_studies/submit_answer', methods=['POST'])
@login_required
def social_studies_submit_answer():
    """社会科問題の回答送信"""
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        user_answer = data.get('answer')
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 問題の正解を取得
                cur.execute('''
                    SELECT correct_answer, acceptable_answers, subject, answer_suffix
                    FROM social_studies_questions 
                    WHERE id = %s
                ''', (question_id,))
                question_data = cur.fetchone()
                
                if not question_data:
                    return jsonify({'error': '問題が見つかりません'}), 404
                
                # 許容回答をパース
                acceptable_answers = []
                if question_data['acceptable_answers']:
                    try:
                        # JSON形式の場合
                        if question_data['acceptable_answers'].startswith('['):
                            acceptable_answers = json.loads(question_data['acceptable_answers'])
                        else:
                            # 文字列形式の場合（カンマ区切り）
                            acceptable_answers = [ans.strip() for ans in question_data['acceptable_answers'].split(',') if ans.strip()]
                    except Exception as e:
                        app.logger.error(f"許容回答パースエラー: {e}, データ: {question_data['acceptable_answers']}")
                        # パースに失敗した場合は単一の文字列として扱う
                        acceptable_answers = [question_data['acceptable_answers'].strip()]
                
                app.logger.info(f"問題ID: {question_id}, 正解: {question_data['correct_answer']}, 許容回答: {acceptable_answers}")
                
                # 回答をチェック（answer_suffixは表示用の補足情報なので、比較には使用しない）
                app.logger.info(f"回答チェック: ユーザー回答='{user_answer}', 正解='{question_data['correct_answer']}'")
                
                is_correct, result_message = check_answer(
                    user_answer, 
                    question_data['correct_answer'], 
                    acceptable_answers
                )
                
                # 学習ログを記録
                cur.execute('''
                    INSERT INTO social_studies_study_log (user_id, question_id, user_answer, is_correct, subject)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (current_user.id, question_id, user_answer, is_correct, question_data['subject']))
                conn.commit()
                
                return jsonify({
                    'is_correct': is_correct,
                    'message': result_message,
                    'correct_answer': question_data['correct_answer']
                })
                
    except Exception as e:
        app.logger.error(f"社会科回答送信エラー: {e}")
        return jsonify({'error': '回答の処理に失敗しました'}), 500

@app.route('/social_studies/admin')
@login_required
def social_studies_admin():
    """社会科管理画面（管理者のみ）- 統合管理画面にリダイレクト"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('login'))
    # 統合管理画面にリダイレクト
    return redirect(url_for('social_studies_admin_unified'))

@app.route('/social_studies/admin/textbook/<int:textbook_id>/unified')
@login_required
def social_studies_admin_textbook_unified(textbook_id):
    """教材別統合管理画面（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    try:
        # フィルターパラメータを取得
        unit_id = request.args.get('unit_id', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        search = request.args.get('search', '').strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 教材情報を取得
                cur.execute('SELECT * FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                textbook = cur.fetchone()
                
                if not textbook:
                    flash('教材が見つかりません', 'error')
                    return redirect(url_for('social_studies_admin_unified'))
                
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) as total_units FROM social_studies_units WHERE textbook_id = %s', (textbook_id,))
                total_units = cur.fetchone()['total_units']
                
                cur.execute('SELECT COUNT(*) as total_questions FROM social_studies_questions WHERE textbook_id = %s', (textbook_id,))
                total_questions = cur.fetchone()['total_questions']
                
                cur.execute('''
                    SELECT COUNT(*) as total_study_logs 
                    FROM social_studies_study_log sl
                    JOIN social_studies_questions q ON sl.question_id = q.id
                    WHERE q.textbook_id = %s
                ''', (textbook_id,))
                total_study_logs = cur.fetchone()['total_study_logs']
                
                # 単元一覧を取得
                cur.execute('''
                    SELECT 
                        u.id, u.name, u.chapter_number, u.description,
                        COUNT(q.id) as question_count
                    FROM social_studies_units u
                    LEFT JOIN social_studies_questions q ON u.id = q.unit_id
                    WHERE u.textbook_id = %s
                    GROUP BY u.id, u.name, u.chapter_number, u.description
                    ORDER BY u.chapter_number, u.name
                ''', (textbook_id,))
                units = cur.fetchall()
                
                # 問題一覧を取得（フィルター適用）
                query = '''
                    SELECT 
                        q.id, q.subject, q.question, q.correct_answer, q.acceptable_answers, 
                        q.difficulty_level, q.created_at,
                        u.name as unit_name
                    FROM social_studies_questions q
                    LEFT JOIN social_studies_units u ON q.unit_id = u.id
                    WHERE q.textbook_id = %s
                '''
                
                # WHERE句の条件を構築
                conditions = []
                params = [textbook_id]
                
                if unit_id:
                    conditions.append('q.unit_id = %s')
                    params.append(int(unit_id))
                
                if difficulty:
                    conditions.append('q.difficulty_level = %s')
                    params.append(difficulty)
                
                if search:
                    conditions.append('(q.question ILIKE %s OR q.correct_answer ILIKE %s)')
                    search_param = f'%{search}%'
                    params.extend([search_param, search_param])
                
                # WHERE句を追加
                if conditions:
                    query += ' AND ' + ' AND '.join(conditions)
                
                # ORDER BY句を追加
                query += ' ORDER BY q.created_at DESC'
                
                # クエリを実行
                cur.execute(query, params)
                questions = cur.fetchall()
                
                return render_template('social_studies/admin_textbook_unified.html',
                                     textbook=textbook,
                                     total_units=total_units,
                                     total_questions=total_questions,
                                     total_study_logs=total_study_logs,
                                     units=units,
                                     questions=questions)
    except Exception as e:
        app.logger.error(f"教材別統合管理画面エラー: {e}")
        flash('教材別統合管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('social_studies_admin_unified'))

@app.route('/social_studies/admin/unified')
@login_required
def social_studies_admin_unified():
    """社会科統合管理画面（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    try:
        # フィルターパラメータを取得
        subject = request.args.get('subject', '').strip()
        textbook_id = request.args.get('textbook_id', '').strip()
        unit_id = request.args.get('unit_id', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        search = request.args.get('search', '').strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) as total_textbooks FROM social_studies_textbooks')
                total_textbooks = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) as total_units FROM social_studies_units')
                total_units = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) as total_questions FROM social_studies_questions')
                total_questions = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) as total_study_logs FROM social_studies_study_log')
                total_study_logs = cur.fetchone()[0]
                
                # 教材一覧を取得
                cur.execute('''
                    SELECT 
                        t.id, t.name, t.subject, t.grade, t.publisher, t.description, t.wasabi_folder_path,
                        COUNT(DISTINCT u.id) as unit_count,
                        COUNT(DISTINCT q.id) as question_count
                    FROM social_studies_textbooks t
                    LEFT JOIN social_studies_units u ON t.id = u.textbook_id
                    LEFT JOIN social_studies_questions q ON t.id = q.textbook_id
                    GROUP BY t.id, t.name, t.subject, t.grade, t.publisher, t.description, t.wasabi_folder_path
                    ORDER BY t.created_at DESC
                ''')
                textbooks = cur.fetchall()
                
                # 問題一覧を取得（フィルター適用）
                query = '''
                    SELECT 
                        q.id, q.subject, q.question, q.correct_answer, q.acceptable_answers, 
                        q.difficulty_level, q.created_at,
                        t.name as textbook_name, u.name as unit_name
                    FROM social_studies_questions q
                    LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN social_studies_units u ON q.unit_id = u.id
                '''
                
                # WHERE句の条件を構築
                conditions = []
                params = []
                
                if subject:
                    conditions.append('q.subject = ?')
                    params.append(subject)
                
                if textbook_id:
                    conditions.append('q.textbook_id = ?')
                    params.append(int(textbook_id))
                
                if unit_id:
                    conditions.append('q.unit_id = ?')
                    params.append(int(unit_id))
                
                if difficulty:
                    conditions.append('q.difficulty_level = ?')
                    params.append(difficulty)
                
                if search:
                    conditions.append('(q.question LIKE ? OR q.correct_answer LIKE ?)')
                    search_param = f'%{search}%'
                    params.extend([search_param, search_param])
                
                # WHERE句を追加
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                
                # ORDER BY句を追加
                query += ' ORDER BY q.created_at DESC'
                
                # クエリを実行
                cur.execute(query, params)
                questions = cur.fetchall()
                
                return render_template('social_studies/admin_unified.html',
                                     total_textbooks=total_textbooks,
                                     total_units=total_units,
                                     total_questions=total_questions,
                                     total_study_logs=total_study_logs,
                                     textbooks=textbooks,
                                     questions=questions)
    except Exception as e:
        app.logger.error(f"社会科統合管理画面エラー: {e}")
        flash('統合管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin'))

@app.route('/social_studies/admin/questions')
@login_required
def social_studies_admin_questions():
    """社会科問題一覧（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    try:
        # フィルターパラメータを取得
        subject = request.args.get('subject', '').strip()
        textbook_id = request.args.get('textbook_id', '').strip()
        unit_id = request.args.get('unit_id', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        search = request.args.get('search', '').strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 基本クエリ
                query = '''
                    SELECT 
                        q.id, q.subject, q.question, q.correct_answer, q.acceptable_answers, 
                        q.difficulty_level, q.created_at,
                        t.name as textbook_name, u.name as unit_name
                    FROM social_studies_questions q
                    LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN social_studies_units u ON q.unit_id = u.id
                '''
                
                # WHERE句の条件を構築
                conditions = []
                params = []
                
                if subject:
                    conditions.append('q.subject = %s')
                    params.append(subject)
                
                if textbook_id:
                    conditions.append('q.textbook_id = %s')
                    params.append(int(textbook_id))
                
                if unit_id:
                    conditions.append('q.unit_id = %s')
                    params.append(int(unit_id))
                
                if difficulty:
                    conditions.append('q.difficulty_level = %s')
                    params.append(difficulty)
                
                if search:
                    conditions.append('(q.question ILIKE %s OR q.correct_answer ILIKE %s)')
                    search_param = f'%{search}%'
                    params.extend([search_param, search_param])
                
                # WHERE句を追加
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                
                # ORDER BY句を追加
                query += ' ORDER BY q.created_at DESC'
                
                # クエリを実行
                cur.execute(query, params)
                questions = cur.fetchall()
                
                return render_template('social_studies/admin_questions.html', questions=questions)
    except Exception as e:
        app.logger.error(f"社会科問題一覧エラー: {e}")
        flash('問題一覧の取得に失敗しました', 'error')
        return redirect(url_for('social_studies_admin'))

@app.route('/social_studies/admin/add_question', methods=['GET', 'POST'])
@login_required
def social_studies_add_question():
    """社会科問題追加（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        subject = request.form['subject']
        textbook_id = request.form.get('textbook_id', '') or None
        unit_id = request.form.get('unit_id', '') or None
        question = request.form['question']
        correct_answer = request.form['correct_answer']
        acceptable_answers = request.form.get('acceptable_answers', '')
        answer_suffix = request.form.get('answer_suffix', '')
        explanation = request.form.get('explanation', '')
        difficulty_level = request.form.get('difficulty_level', 'basic')
        image_name = request.form.get('image_name', '').strip()
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 問題を追加
                    cur.execute('''
                        INSERT INTO social_studies_questions 
                        (subject, textbook_id, unit_id, question, correct_answer, acceptable_answers, answer_suffix, explanation, difficulty_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (subject, textbook_id, unit_id, question, correct_answer, acceptable_answers, answer_suffix, explanation, difficulty_level))
                    
                    question_id = cur.fetchone()[0]
                    
                    # 画像名が指定されている場合、Wasabiから画像URLを取得して更新
                    if image_name and textbook_id:
                        try:
                            # 教材のフォルダパスを取得
                            cur.execute('SELECT wasabi_folder_path FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                            result = cur.fetchone()
                            if result and result[0]:
                                folder_path = result[0]
                                
                                # Wasabiで画像を検索
                                s3_client = init_wasabi_client()
                                if s3_client:
                                    bucket_name = os.getenv('WASABI_BUCKET')
                                    endpoint = os.getenv('WASABI_ENDPOINT')
                                    
                                    # 複数の拡張子で試行
                                    extensions = ['jpg', 'jpeg', 'png', 'gif']
                                    found_image_url = None
                                    
                                    for ext in extensions:
                                        try:
                                            image_key = f"{folder_path}/{image_name}.{ext}"
                                            s3_client.head_object(Bucket=bucket_name, Key=image_key)
                                            found_image_url = f"{endpoint}/{bucket_name}/{image_key}"
                                            break
                                        except Exception:
                                            continue
                                    
                                    if found_image_url:
                                        # 問題に画像URLを設定
                                        cur.execute('''
                                            UPDATE social_studies_questions 
                                            SET image_url = %s 
                                            WHERE id = %s
                                        ''', (found_image_url, question_id))
                                        app.logger.info(f"問題ID {question_id} に画像URLを設定: {found_image_url}")
                                    else:
                                        app.logger.warning(f"画像が見つかりません: {image_name} in {folder_path}")
                        except Exception as e:
                            app.logger.error(f"画像URL設定エラー: {e}")
                    
                    conn.commit()
                    flash('問題が追加されました', 'success')
                    
                    # 単元が指定されている場合は単元問題一覧に戻る
                    if unit_id:
                        return redirect(url_for('social_studies_admin_unit_questions', textbook_id=textbook_id, unit_id=unit_id))
                    # 教材が指定されている場合は統一管理画面に戻る
                    elif textbook_id:
                        return redirect(url_for('social_studies_admin_textbook_unified', textbook_id=textbook_id))
                    else:
                        return redirect(url_for('social_studies_admin_questions'))
        except Exception as e:
            app.logger.error(f"社会科問題追加エラー: {e}")
            flash('問題の追加に失敗しました', 'error')
    
    # GETリクエストの場合、URLパラメータから教材IDと単元IDを取得
    textbook_id = request.args.get('textbook_id')
    unit_id = request.args.get('unit_id')
    
    # 教材と単元の情報を取得
    textbook_info = None
    unit_info = None
    
    if textbook_id:
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SELECT id, name, subject, wasabi_folder_path FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                    textbook_info = cur.fetchone()
                    
                    if unit_id:
                        cur.execute('SELECT id, name, chapter_number FROM social_studies_units WHERE id = %s AND textbook_id = %s', (unit_id, textbook_id))
                        unit_info = cur.fetchone()
        except Exception as e:
            app.logger.error(f"教材・単元情報取得エラー: {e}")
    
    return render_template('social_studies/add_question.html', 
                         textbook_id=textbook_id, unit_id=unit_id,
                         textbook_info=textbook_info, unit_info=unit_info)

@app.route('/social_studies/admin/delete_question/<int:question_id>', methods=['POST'])
@login_required
def social_studies_delete_question(question_id):
    """社会科問題削除（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 問題が存在するかチェック
                cur.execute('SELECT id FROM social_studies_questions WHERE id = %s', (question_id,))
                if not cur.fetchone():
                    return jsonify({'error': '問題が見つかりません'}), 404
                
                # 関連する学習ログを削除
                cur.execute('DELETE FROM social_studies_study_log WHERE question_id = %s', (question_id,))
                
                # 問題を削除
                cur.execute('DELETE FROM social_studies_questions WHERE id = %s', (question_id,))
                conn.commit()
                
                return jsonify({'success': True, 'message': '問題が削除されました'})
                
    except Exception as e:
        app.logger.error(f"社会科問題削除エラー: {e}")
        return jsonify({'error': '問題の削除に失敗しました'}), 500

@app.route('/social_studies/admin/bulk_delete_questions', methods=['POST'])
@login_required
def social_studies_bulk_delete_questions():
    """社会科問題一括削除（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return jsonify({'error': '削除する問題が選択されていません'}), 400
        
        # 数値のリストに変換
        try:
            question_ids = [int(qid) for qid in question_ids]
        except (ValueError, TypeError):
            return jsonify({'error': '無効な問題IDが含まれています'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 問題が存在するかチェック
                placeholders = ','.join(['%s'] * len(question_ids))
                cur.execute(f'SELECT id FROM social_studies_questions WHERE id IN ({placeholders})', question_ids)
                existing_questions = cur.fetchall()
                
                if len(existing_questions) != len(question_ids):
                    return jsonify({'error': '一部の問題が見つかりません'}), 404
                
                # 関連する学習ログを削除
                cur.execute(f'DELETE FROM social_studies_study_log WHERE question_id IN ({placeholders})', question_ids)
                
                # 問題を削除
                cur.execute(f'DELETE FROM social_studies_questions WHERE id IN ({placeholders})', question_ids)
                deleted_count = cur.rowcount
                conn.commit()
                
                return jsonify({
                    'success': True, 
                    'message': f'{deleted_count}件の問題が削除されました',
                    'deleted_count': deleted_count
                })
                
    except Exception as e:
        app.logger.error(f"社会科問題一括削除エラー: {e}")
        return jsonify({'error': '問題の一括削除に失敗しました'}), 500

@app.route('/social_studies/admin/edit_question_page/<int:question_id>', methods=['GET'])
@login_required
def social_studies_edit_question_page(question_id):
    """問題編集ページ表示（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 問題データを取得
                cur.execute('''
                    SELECT q.id, q.subject, q.textbook_id, q.unit_id, q.question, q.correct_answer, 
                           q.acceptable_answers, q.answer_suffix, q.explanation, q.difficulty_level,
                           q.image_name, q.image_url, q.image_title, t.name as textbook_name, u.name as unit_name,
                           t.subject as textbook_subject, u.chapter_number
                    FROM social_studies_questions q
                    LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN social_studies_units u ON q.unit_id = u.id
                    WHERE q.id = %s
                ''', (question_id,))
                question = cur.fetchone()
                
                if not question:
                    flash('問題が見つかりません', 'error')
                    return redirect(url_for('social_studies_admin_questions'))
                
                # 教材と単元の情報を取得
                textbook_info = None
                unit_info = None
                image_path_info = None
                
                if question['textbook_id']:
                    cur.execute('SELECT * FROM social_studies_textbooks WHERE id = %s', (question['textbook_id'],))
                    textbook_info = cur.fetchone()
                
                if question['unit_id']:
                    cur.execute('SELECT * FROM social_studies_units WHERE id = %s', (question['unit_id'],))
                    unit_info = cur.fetchone()
                
                # 画像パス情報を生成
                if textbook_info and unit_info:
                    chapter_number = unit_info['chapter_number'] or 1
                    base_image_url = f"https://s3.ap-northeast-1-ntt.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{textbook_info['wasabi_folder_path']}/{chapter_number}"
                    
                    # この単元に画像が設定されている問題数を取得
                    cur.execute('''
                        SELECT COUNT(*) as count
                        FROM social_studies_questions
                        WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
                    ''', (question['textbook_id'], question['unit_id']))
                    image_questions_count = cur.fetchone()['count']
                    
                    image_path_info = {
                        'base_url': base_image_url,
                        'chapter_number': chapter_number,
                        'wasabi_folder_path': textbook_info['wasabi_folder_path'],
                        'image_questions_count': image_questions_count
                    }
                
                return render_template('social_studies/edit_question.html', 
                                     question=question, 
                                     textbook_info=textbook_info, 
                                     unit_info=unit_info,
                                     image_path_info=image_path_info)
    except Exception as e:
        app.logger.error(f"問題編集ページ表示エラー: {e}")
        flash('問題編集ページの表示に失敗しました', 'error')
        return redirect(url_for('social_studies_admin_questions'))

@app.route('/social_studies/admin/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def social_studies_edit_question(question_id):
    """社会科問題編集（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    if request.method == 'GET':
        # 問題データを取得
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('''
                        SELECT q.id, q.subject, q.textbook_id, q.unit_id, q.question, q.correct_answer, 
                               q.acceptable_answers, q.answer_suffix, q.explanation, q.difficulty_level,
                               q.image_name, q.image_url, q.image_title, t.name as textbook_name, u.name as unit_name
                        FROM social_studies_questions q
                        LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
                        LEFT JOIN social_studies_units u ON q.unit_id = u.id
                        WHERE q.id = %s
                    ''', (question_id,))
                    question = cur.fetchone()
                    
                    if not question:
                        return jsonify({'error': '問題が見つかりません'}), 404
                    
                    return jsonify(dict(question))
        except Exception as e:
            app.logger.error(f"問題取得エラー: {e}")
            return jsonify({'error': '問題の取得に失敗しました'}), 500
    
    elif request.method == 'POST':
        # 問題データを更新
        try:
            data = request.get_json()
            subject = data.get('subject', '').strip()
            textbook_id = data.get('textbook_id')
            unit_id = data.get('unit_id')
            question_text = data.get('question', '').strip()
            correct_answer = data.get('correct_answer', '').strip()
            acceptable_answers = data.get('acceptable_answers', '').strip()
            answer_suffix = data.get('answer_suffix', '').strip()
            explanation = data.get('explanation', '').strip()
            difficulty_level = data.get('difficulty_level', 'basic')
            image_name = data.get('image_name', '').strip()
            image_title = data.get('image_name', '').strip()  # image_nameをimage_titleとしても使用
            
            # バリデーション
            if not question_text or not correct_answer:
                return jsonify({'error': '問題文と正解は必須です'}), 400
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 問題が存在するかチェック
                    cur.execute('SELECT id FROM social_studies_questions WHERE id = %s', (question_id,))
                    if not cur.fetchone():
                        return jsonify({'error': '問題が見つかりません'}), 404
                    
                    # 問題を更新
                    cur.execute('''
                        UPDATE social_studies_questions 
                        SET subject = %s, textbook_id = %s, unit_id = %s, question = %s, 
                            correct_answer = %s, acceptable_answers = %s, answer_suffix = %s,
                            explanation = %s, difficulty_level = %s, image_name = %s, image_title = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (subject, textbook_id, unit_id, question_text, correct_answer, 
                          acceptable_answers, answer_suffix, explanation, difficulty_level, 
                          image_name, image_title, question_id))
                    
                    # 画像名が指定されている場合、Wasabiから画像URLを取得して更新
                    if image_name and textbook_id:
                        try:
                            # 教材のフォルダパスを取得
                            cur.execute('SELECT wasabi_folder_path FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                            result = cur.fetchone()
                            if result and result[0]:
                                folder_path = result[0]
                                
                                # Wasabiで画像を検索
                                s3_client = init_wasabi_client()
                                if s3_client:
                                    bucket_name = os.getenv('WASABI_BUCKET')
                                    endpoint = os.getenv('WASABI_ENDPOINT')
                                    
                                    # 複数の拡張子で試行
                                    extensions = ['jpg', 'jpeg', 'png', 'gif']
                                    found_image_url = None
                                    
                                    for ext in extensions:
                                        try:
                                            image_key = f"{folder_path}/{image_name}.{ext}"
                                            s3_client.head_object(Bucket=bucket_name, Key=image_key)
                                            found_image_url = f"{endpoint}/{bucket_name}/{image_key}"
                                            break
                                        except Exception:
                                            continue
                                    
                                    if found_image_url:
                                        # 問題に画像URLを設定
                                        cur.execute('''
                                            UPDATE social_studies_questions 
                                            SET image_url = %s 
                                            WHERE id = %s
                                        ''', (found_image_url, question_id))
                                        app.logger.info(f"問題ID {question_id} に画像URLを設定: {found_image_url}")
                                    else:
                                        app.logger.warning(f"画像が見つかりません: {image_name} in {folder_path}")
                        except Exception as e:
                            app.logger.error(f"画像URL設定エラー: {e}")
                    
                    conn.commit()
                    
                    return jsonify({'success': True, 'message': '問題が更新されました'})
                    
        except Exception as e:
            app.logger.error(f"問題更新エラー: {e}")
            return jsonify({'error': '問題の更新に失敗しました'}), 500

# ========== 教材管理 ==========

# 教材管理ルートは削除 - 統一管理画面で代替

@app.route('/social_studies/admin/add_unit/<int:textbook_id>', methods=['GET', 'POST'])
@login_required
def social_studies_add_unit(textbook_id):
    """単元追加（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 教材情報を取得
                cur.execute('SELECT * FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                textbook = cur.fetchone()
                
                if not textbook:
                    flash('教材が見つかりません', 'error')
                    return redirect(url_for('social_studies_admin_unified'))
                
                if request.method == 'POST':
                    name = request.form['name']
                    chapter_number = request.form.get('chapter_number', '') or None
                    description = request.form.get('description', '')
                    
                    # 章番号が指定されていない場合、自動的に次の番号を割り当て
                    if not chapter_number:
                        cur.execute('SELECT MAX(chapter_number) as max_num FROM social_studies_units WHERE textbook_id = %s', (textbook_id,))
                        result = cur.fetchone()
                        chapter_number = (result['max_num'] or 0) + 1
                    
                    cur.execute('''
                        INSERT INTO social_studies_units (textbook_id, name, chapter_number, description)
                        VALUES (%s, %s, %s, %s)
                    ''', (textbook_id, name, chapter_number, description))
                    conn.commit()
                    flash('単元が追加されました', 'success')
                    return redirect(url_for('social_studies_admin_textbook_unified', textbook_id=textbook_id))
                
                return render_template('social_studies/add_unit.html', textbook=textbook)
    except Exception as e:
        app.logger.error(f"単元追加エラー: {e}")
        flash('単元の追加に失敗しました', 'error')
        return redirect(url_for('social_studies_admin_textbook_unified', textbook_id=textbook_id))

@app.route('/social_studies/admin/delete_unit/<int:unit_id>', methods=['POST'])
@login_required
def social_studies_delete_unit(unit_id):
    """単元削除（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 単元が存在するかチェック
                cur.execute('SELECT id FROM social_studies_units WHERE id = %s', (unit_id,))
                if not cur.fetchone():
                    return jsonify({'error': '単元が見つかりません'}), 404
                
                # 関連する問題の学習ログを削除
                cur.execute('''
                    DELETE FROM social_studies_study_log 
                    WHERE question_id IN (
                        SELECT id FROM social_studies_questions WHERE unit_id = %s
                    )
                ''', (unit_id,))
                
                # 関連する問題を削除
                cur.execute('DELETE FROM social_studies_questions WHERE unit_id = %s', (unit_id,))
                
                # 単元を削除
                cur.execute('DELETE FROM social_studies_units WHERE id = %s', (unit_id,))
                conn.commit()
                
                return jsonify({'success': True, 'message': '単元が削除されました'})
                
    except Exception as e:
        app.logger.error(f"単元削除エラー: {e}")
        return jsonify({'error': '単元の削除に失敗しました'}), 500

@app.route('/social_studies/admin/edit_unit/<int:unit_id>', methods=['GET', 'POST'])
@login_required
def social_studies_edit_unit(unit_id):
    """単元編集（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    if request.method == 'GET':
        # 単元データを取得
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('''
                        SELECT id, name, chapter_number, description
                        FROM social_studies_units 
                        WHERE id = %s
                    ''', (unit_id,))
                    unit = cur.fetchone()
                    
                    if not unit:
                        return jsonify({'error': '単元が見つかりません'}), 404
                    
                    return jsonify(dict(unit))
        except Exception as e:
            app.logger.error(f"単元取得エラー: {e}")
            return jsonify({'error': '単元の取得に失敗しました'}), 500
    
    elif request.method == 'POST':
        # 単元データを更新
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            chapter_number = data.get('chapter_number', '').strip()
            description = data.get('description', '').strip()
            
            # バリデーション
            if not name:
                return jsonify({'error': '単元名は必須です'}), 400
            
            # chapter_numberを数値に変換（空の場合はNULL）
            chapter_number_int = None
            if chapter_number:
                try:
                    chapter_number_int = int(chapter_number)
                except ValueError:
                    return jsonify({'error': '章番号は数値で入力してください'}), 400
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 単元が存在するかチェック
                    cur.execute('SELECT id FROM social_studies_units WHERE id = %s', (unit_id,))
                    if not cur.fetchone():
                        return jsonify({'error': '単元が見つかりません'}), 404
                    
                    # 単元を更新
                    cur.execute('''
                        UPDATE social_studies_units 
                        SET name = %s, chapter_number = %s, description = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (name, chapter_number_int, description, unit_id))
                    conn.commit()
                    
                    return jsonify({'success': True, 'message': '単元が更新されました'})
                    
        except Exception as e:
            app.logger.error(f"単元更新エラー: {e}")
            return jsonify({'error': '単元の更新に失敗しました'}), 500

# ========== API エンドポイント ==========

@app.route('/social_studies/api/textbooks')
@login_required
def social_studies_api_textbooks():
    """教材一覧API"""
    subject = request.args.get('subject')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if subject:
                    cur.execute('''
                        SELECT id, name, subject, grade, publisher
                        FROM social_studies_textbooks 
                        WHERE subject = %s
                        ORDER BY name
                    ''', (subject,))
                else:
                    cur.execute('''
                        SELECT id, name, subject, grade, publisher
                        FROM social_studies_textbooks 
                        ORDER BY subject, name
                    ''')
                textbooks = cur.fetchall()
                return jsonify(textbooks)
    except Exception as e:
        app.logger.error(f"教材APIエラー: {e}")
        return jsonify({'error': '教材の取得に失敗しました'}), 500

@app.route('/social_studies/api/textbook/<int:textbook_id>')
@login_required
def social_studies_api_textbook_detail(textbook_id):
    """教材詳細API（wasabi_folder_pathを含む）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT id, name, subject, grade, publisher, wasabi_folder_path
                    FROM social_studies_textbooks 
                    WHERE id = %s
                ''', (textbook_id,))
                textbook = cur.fetchone()
                
                if not textbook:
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                return jsonify(dict(textbook))
    except Exception as e:
        app.logger.error(f"教材詳細APIエラー: {e}")
        return jsonify({'error': '教材の取得に失敗しました'}), 500

@app.route('/social_studies/api/units')
@login_required
def social_studies_api_units():
    """単元一覧API"""
    textbook_id = request.args.get('textbook_id')
    
    if not textbook_id:
        return jsonify({'error': '教材IDが必要です'}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT id, name, chapter_number, description
                    FROM social_studies_units 
                    WHERE textbook_id = %s
                    ORDER BY chapter_number, name
                ''', (textbook_id,))
                units = cur.fetchall()
                return jsonify(units)
    except Exception as e:
        app.logger.error(f"単元APIエラー: {e}")
        return jsonify({'error': '単元の取得に失敗しました'}), 500

@app.route('/social_studies/api/check_image')
@login_required
def social_studies_api_check_image():
    """画像存在確認API（単元の章番号に基づくフォルダ検索）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        image_name = request.args.get('image_name', '').strip()
        unit_id = request.args.get('unit_id')
        
        app.logger.info(f"🔍 画像確認API呼び出し: image_name='{image_name}', unit_id='{unit_id}'")
        
        if not image_name or not unit_id:
            app.logger.warning("❌ パラメータ不足")
            return jsonify({'exists': False, 'error': '画像名と単元IDが必要です'})
        
        # 単元の章番号に基づいてフォルダパスを生成
        folder_path = get_unit_image_folder_path_by_unit_id(unit_id)
        
        # Wasabiで画像を検索
        s3_client = init_wasabi_client()
        if not s3_client:
            app.logger.error("❌ Wasabiクライアント初期化失敗")
            return jsonify({'exists': False, 'error': 'Wasabi接続エラー'})
        
        bucket_name = os.getenv('WASABI_BUCKET')
        endpoint = os.getenv('WASABI_ENDPOINT')
        
        app.logger.info(f"🔍 Wasabi検索: bucket={bucket_name}, endpoint={endpoint}")
        
        # 複数の拡張子で試行
        extensions = ['jpg', 'jpeg', 'png', 'gif']
        found_image = None
        found_extension = None
        
        for ext in extensions:
            try:
                image_key = f"{folder_path}/{image_name}.{ext}"
                app.logger.info(f"🔍 試行中: {image_key}")
                s3_client.head_object(Bucket=bucket_name, Key=image_key)
                found_image = f"{endpoint}/{bucket_name}/{image_key}"
                found_extension = ext
                app.logger.info(f"✅ 画像発見: {found_image}")
                break
            except Exception as e:
                app.logger.debug(f"❌ 拡張子 {ext} で失敗: {str(e)}")
                continue
        
        if found_image:
            app.logger.info(f"✅ 画像確認成功: {found_image}")
            
            # 画像の公開アクセス権限を確認・設定
            try:
                success, error = set_image_public_access(found_image)
                if success:
                    app.logger.info(f"✅ 画像公開アクセス設定完了: {found_image}")
                else:
                    app.logger.warning(f"⚠️ 画像公開アクセス設定失敗: {error}")
            except Exception as e:
                app.logger.warning(f"⚠️ 画像公開アクセス設定エラー: {e}")
            
            return jsonify({
                'exists': True,
                'image_url': found_image,
                'folder_path': folder_path,
                'extension': found_extension
            })
        else:
            app.logger.warning(f"❌ 画像未発見: フォルダ「{folder_path}」に「{image_name}」の画像が見つかりません")
            return jsonify({
                'exists': False,
                'folder_path': folder_path,
                'message': f'フォルダ「{folder_path}」に「{image_name}」の画像が見つかりません'
            })
                
    except Exception as e:
        app.logger.error(f"❌ 画像確認エラー: {e}")
        return jsonify({'exists': False, 'error': f'画像確認に失敗しました: {str(e)}'}), 500

@app.route('/social_studies/api/set_image_public/<int:question_id>', methods=['POST'])
@login_required
def social_studies_api_set_image_public(question_id):
    """問題の画像に公開アクセス権限を設定（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # 問題の画像URLを取得
        with get_db_connection() as conn:
                cur.execute('SELECT image_url FROM social_studies_questions WHERE id = %s', (question_id,))
                result = cur.fetchone()
                if not result or not result[0]:
                    return jsonify({'error': 'この問題には画像が設定されていません'}), 404
                
                image_url = result[0]
        
        # 公開アクセス権限を設定
        success, error = set_image_public_access(image_url)
        
        if success:
            app.logger.info(f"✅ 問題ID {question_id} の画像公開アクセス設定完了: {image_url}")
            return jsonify({
                'success': True,
                'message': '画像の公開アクセス権限を設定しました',
                'image_url': image_url
            })
        else:
            app.logger.error(f"❌ 問題ID {question_id} の画像公開アクセス設定失敗: {error}")
            return jsonify({'error': f'画像の公開アクセス権限設定に失敗しました: {error}'}), 500
            
    except Exception as e:
        app.logger.error(f"❌ 画像公開アクセス設定エラー: {e}")
        return jsonify({'error': f'画像公開アクセス設定に失敗しました: {str(e)}'}), 500

# ========== 教材管理 ==========

@app.route('/social_studies/admin/add_textbook', methods=['GET', 'POST'])
@login_required
def social_studies_add_textbook():
    """教材追加（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        name = request.form['name']
        subject = request.form['subject']
        grade = request.form.get('grade', '')
        publisher = request.form.get('publisher', '')
        description = request.form.get('description', '')
        wasabi_folder_path = request.form.get('wasabi_folder_path', '').strip()
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO social_studies_textbooks 
                        (name, subject, grade, publisher, description, wasabi_folder_path)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (name, subject, grade, publisher, description, wasabi_folder_path))
                    conn.commit()
                    flash('教材が追加されました', 'success')
                    return redirect(url_for('social_studies_admin_unified'))
        except Exception as e:
            app.logger.error(f"教材追加エラー: {e}")
            flash('教材の追加に失敗しました', 'error')
        
    return render_template('social_studies/add_textbook.html')

@app.route('/social_studies/admin/edit_textbook/<int:textbook_id>', methods=['GET', 'POST'])
@login_required
def social_studies_edit_textbook(textbook_id):
    """教材編集（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    if request.method == 'GET':
        # 教材データを取得
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('''
                        SELECT id, name, subject, grade, publisher, description, wasabi_folder_path
                        FROM social_studies_textbooks 
                        WHERE id = %s
                    ''', (textbook_id,))
                    textbook = cur.fetchone()
                    
                    if not textbook:
                        return jsonify({'error': '教材が見つかりません'}), 404
                    
                    return jsonify(dict(textbook))
        except Exception as e:
            app.logger.error(f"教材取得エラー: {e}")
            return jsonify({'error': '教材の取得に失敗しました'}), 500
    
    elif request.method == 'POST':
        # 教材データを更新
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            subject = data.get('subject', '').strip()
            grade = data.get('grade', '').strip()
            publisher = data.get('publisher', '').strip()
            description = data.get('description', '').strip()
            wasabi_folder_path = data.get('wasabi_folder_path', '').strip()
            
            # バリデーション
            if not name:
                return jsonify({'error': '教材名は必須です'}), 400
            
            if not subject:
                return jsonify({'error': '科目は必須です'}), 400
            
            if subject not in ['地理', '歴史', '公民', '理科']:
                return jsonify({'error': '無効な科目です'}), 400
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 教材が存在するかチェック
                    cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                    if not cur.fetchone():
                        return jsonify({'error': '教材が見つかりません'}), 404
                    
                    # 教材を更新
                    cur.execute('''
                        UPDATE social_studies_textbooks 
                        SET name = %s, subject = %s, grade = %s, publisher = %s, description = %s, wasabi_folder_path = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (name, subject, grade, publisher, description, wasabi_folder_path, textbook_id))
                    conn.commit()
                    
                    return jsonify({'success': True, 'message': '教材が更新されました'})
                    
        except Exception as e:
            app.logger.error(f"教材更新エラー: {e}")
            return jsonify({'error': '教材の更新に失敗しました'}), 500

@app.route('/social_studies/admin/delete_textbook/<int:textbook_id>', methods=['POST'])
@login_required
def social_studies_delete_textbook(textbook_id):
    """教材削除（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 教材が存在するかチェック
                cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                if not cur.fetchone():
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                # 関連する問題の学習ログを削除
                cur.execute('''
                    DELETE FROM social_studies_study_log 
                    WHERE question_id IN (
                        SELECT id FROM social_studies_questions WHERE textbook_id = %s
                    )
                ''', (textbook_id,))
                
                # 関連する問題を削除
                cur.execute('DELETE FROM social_studies_questions WHERE textbook_id = %s', (textbook_id,))
                
                # 関連する単元を削除
                cur.execute('DELETE FROM social_studies_units WHERE textbook_id = %s', (textbook_id,))
                
                # 教材を削除
                cur.execute('DELETE FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                conn.commit()
                
                return jsonify({'success': True, 'message': '教材が削除されました'})
                
    except Exception as e:
        app.logger.error(f"教材削除エラー: {e}")
        return jsonify({'error': '教材の削除に失敗しました'}), 500

# 管理機能は routes/admin.py に移動済み

@app.route('/social_studies/admin/upload_csv', methods=['POST'])
@login_required
def social_studies_upload_csv():
    """社会科問題CSV一括登録（統合管理画面用）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    if 'csv_file' not in request.files:
        return jsonify({'error': 'CSVファイルが選択されていません'}), 400
    
    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'error': 'CSVファイルが選択されていません'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'CSVファイルを選択してください'}), 400
    
    # 教材IDを取得（教材別アップロードの場合）
    textbook_id = request.form.get('textbook_id')
    
    try:
        # CSVファイルを読み込み
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        if len(lines) < 2:
            return jsonify({'error': 'CSVファイルが空です'}), 400
        
        # ヘッダー行をスキップ
        data_lines = lines[1:]
        
        imported_count = 0
        error_count = 0
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for i, line in enumerate(data_lines, 2):
                    try:
                        # カンマで分割（ただし、ダブルクォート内のカンマは無視）
                        import csv
                        from io import StringIO
                        
                        csv_reader = csv.reader(StringIO(line))
                        row = next(csv_reader)
                        
                        # 教材別アップロードの場合は列数が少ない
                        if textbook_id:
                            if len(row) < 5:
                                app.logger.warning(f"行 {i}: 列数が不足しています")
                                error_count += 1
                                continue
                            
                            unit_id = row[0].strip() if row[0].strip() else None
                            question = row[1].strip()
                            correct_answer = row[2].strip()
                            explanation = row[3].strip() if len(row) > 3 else ''
                            difficulty_level = row[4].strip() if len(row) > 4 else 'basic'
                            subject = None  # 教材から取得
                        else:
                            if len(row) < 7:
                                app.logger.warning(f"行 {i}: 列数が不足しています")
                                error_count += 1
                                continue
                            
                            subject = row[0].strip()
                            unit_id = row[2].strip() if row[2].strip() else None
                            question = row[3].strip()
                            correct_answer = row[4].strip()
                            explanation = row[5].strip() if len(row) > 5 else ''
                            difficulty_level = row[6].strip() if len(row) > 6 else 'basic'
                        
                        # 必須項目のチェック
                        if not question or not correct_answer:
                            app.logger.warning(f"行 {i}: 必須項目が不足しています")
                            error_count += 1
                            continue
                        
                        # 教材別アップロードの場合は教材の科目を取得
                        if textbook_id:
                            cur.execute('SELECT subject FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                            result = cur.fetchone()
                            if not result:
                                app.logger.warning(f"行 {i}: 無効な教材IDです: {textbook_id}")
                                error_count += 1
                                continue
                            subject = result[0]
                        else:
                            # 科目の妥当性チェック
                            if subject not in ['地理', '歴史', '公民', '理科']:
                                app.logger.warning(f"行 {i}: 無効な科目です: {subject}")
                                error_count += 1
                                continue
                        
                        # 難易度の妥当性チェック
                        if difficulty_level not in ['basic', 'intermediate', 'advanced']:
                            difficulty_level = 'basic'
                        
                        # 単元IDの妥当性チェック
                        if unit_id:
                            try:
                                unit_id = int(unit_id)
                                if textbook_id:
                                    # 教材別アップロードの場合は教材に属する単元かチェック
                                    cur.execute('SELECT id FROM social_studies_units WHERE id = %s AND textbook_id = %s', (unit_id, textbook_id))
                                else:
                                    cur.execute('SELECT id FROM social_studies_units WHERE id = %s', (unit_id,))
                                if not cur.fetchone():
                                    app.logger.warning(f"行 {i}: 無効な単元IDです: {unit_id}")
                                    unit_id = None
                            except ValueError:
                                app.logger.warning(f"行 {i}: 無効な単元IDです: {unit_id}")
                                unit_id = None
                        
                        # 問題を挿入
                        cur.execute('''
                                INSERT INTO social_studies_questions 
                                (subject, textbook_id, unit_id, question, correct_answer, explanation, difficulty_level)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ''', (subject, textbook_id, unit_id, question, correct_answer, explanation, difficulty_level))
                        
                        imported_count += 1
                        
                    except Exception as e:
                        app.logger.error(f"行 {i} の処理エラー: {e}")
                        error_count += 1
                        continue
                
                conn.commit()
        
        if error_count > 0:
            return jsonify({
                'imported_count': imported_count,
                'error_count': error_count,
                'message': f'{imported_count}件の問題をインポートしました（{error_count}件エラー）'
            })
        else:
            return jsonify({
                'imported_count': imported_count,
                'message': f'{imported_count}件の問題をインポートしました'
            })
            
    except Exception as e:
        app.logger.error(f"CSVアップロードエラー: {e}")
        return jsonify({'error': 'CSVファイルの処理に失敗しました'}), 500

@app.route('/social_studies/admin/upload_units_csv', methods=['POST'])
@login_required
def social_studies_upload_units_csv():
    """単元CSV一括登録（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    if 'csv_file' not in request.files:
        return jsonify({'error': 'CSVファイルが選択されていません'}), 400
    
    file = request.files['csv_file']
    textbook_id = request.form.get('textbook_id')
    
    if file.filename == '':
        return jsonify({'error': 'CSVファイルが選択されていません'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'CSVファイルを選択してください'}), 400
    
    if not textbook_id:
        return jsonify({'error': '教材IDが指定されていません'}), 400
    
    try:
        # CSVファイルを読み込み
        content = file.read().decode('utf-8')
        lines = content.strip().split('\n')
        
        if len(lines) < 2:
            return jsonify({'error': 'CSVファイルが空です'}), 400
        
        # ヘッダー行をスキップ
        data_lines = lines[1:]
        
        imported_count = 0
        error_count = 0
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 教材が存在するかチェック
                cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                if not cur.fetchone():
                    return jsonify({'error': '指定された教材が見つかりません'}), 400
                
                for i, line in enumerate(data_lines, 2):
                    try:
                        # カンマで分割
                        import csv
                        from io import StringIO
                        
                        csv_reader = csv.reader(StringIO(line))
                        row = next(csv_reader)
                        
                        if len(row) < 1:
                            app.logger.warning(f"行 {i}: 列数が不足しています")
                            error_count += 1
                            continue
                        
                        name = row[0].strip()
                        chapter_number = row[1].strip() if len(row) > 1 and row[1].strip() else None
                        description = row[2].strip() if len(row) > 2 and row[2].strip() else ''
                        
                        # 必須項目のチェック
                        if not name:
                            app.logger.warning(f"行 {i}: 単元名が空です")
                            error_count += 1
                            continue
                        
                        # 章番号の妥当性チェック
                        chapter_number_int = None
                        if chapter_number:
                            try:
                                chapter_number_int = int(chapter_number)
                                if chapter_number_int < 1:
                                    app.logger.warning(f"行 {i}: 章番号は1以上の数値で入力してください")
                                    error_count += 1
                                    continue
                            except ValueError:
                                app.logger.warning(f"行 {i}: 章番号は数値で入力してください")
                                error_count += 1
                                continue
                        
                        # 単元を挿入
                        cur.execute('''
                            INSERT INTO social_studies_units 
                            (textbook_id, name, chapter_number, description)
                            VALUES (%s, %s, %s, %s)
                        ''', (textbook_id, name, chapter_number_int, description))
                        
                        imported_count += 1
                        
                    except Exception as e:
                        app.logger.error(f"行 {i} の処理エラー: {e}")
                        error_count += 1
                        continue
                
                conn.commit()
        
        if error_count > 0:
            return jsonify({
                'imported_count': imported_count,
                'error_count': error_count,
                'message': f'{imported_count}件の単元をインポートしました（{error_count}件エラー）'
            })
        else:
            return jsonify({
                'imported_count': imported_count,
                'message': f'{imported_count}件の単元をインポートしました'
            })
            
    except Exception as e:
        app.logger.error(f"単元CSVアップロードエラー: {e}")
        return jsonify({'error': 'CSVファイルの処理に失敗しました'}), 500

@app.route('/social_studies/admin/upload_questions_csv', methods=['POST'])
@login_required
def social_studies_upload_questions_csv():
    """社会科問題CSV一括登録（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        default_subject = request.form.get('default_subject', '').strip()
        default_textbook_id = request.form.get('default_textbook_id', '').strip()
        
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'CSVファイルを選択してください'}), 400
        
        # CSVファイルを読み込み（複数エンコーディング対応）
        file_content = file.read()
        csv_data = None
        
        # 複数のエンコーディングを試行
        encodings = ['utf-8-sig', 'utf-8', 'shift_jis', 'cp932', 'euc-jp', 'iso-2022-jp']
        for encoding in encodings:
            try:
                csv_data = file_content.decode(encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue
        
        if csv_data is None:
            return jsonify({'error': 'CSVファイルのエンコーディングを認識できませんでした。UTF-8、Shift_JIS、CP932、EUC-JP、ISO-2022-JPのいずれかで保存してください。'}), 400
        
        if len(csv_data) < 2:  # ヘッダー行 + データ行が最低1行必要
            return jsonify({'error': 'CSVファイルにデータが含まれていません'}), 400
        
        if len(csv_data) > 1001:  # ヘッダー行 + 最大1000行
            return jsonify({'error': 'CSVファイルは最大1000行までです'}), 400
        
        reader = csv.DictReader(csv_data)
        registered_count = 0
        skipped_count = 0
        
        app.logger.info(f"CSVアップロード開始: {len(csv_data)}行のデータ")
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for row_num, row in enumerate(reader, 1):
                    app.logger.info(f"行{row_num}を処理中: {row}")
                    try:
                        # 必須フィールドの取得
                        subject = row.get('subject', '').strip() or default_subject
                        question = row.get('question', '').strip()
                        correct_answer = row.get('correct_answer', '').strip()
                        
                        # バリデーション
                        if not subject or not question or not correct_answer:
                            app.logger.warning(f"行{row_num}: 必須フィールドが不足 - subject: '{subject}', question: '{question}', correct_answer: '{correct_answer}'")
                            skipped_count += 1
                            continue
                        
                        # オプションフィールドの取得
                        acceptable_answers = row.get('acceptable_answers', '').strip()
                        explanation = row.get('explanation', '').strip()
                        answer_suffix = row.get('answer_suffix', '').strip()
                        
                        # 新しいCSVフォーマット対応
                        # 教材情報の処理
                        textbook_id = None
                        textbook_name = row.get('textbook_name', '').strip()
                        textbook_grade = row.get('textbook_grade', '').strip()
                        textbook_publisher = row.get('textbook_publisher', '').strip()
                        textbook_wasabi_folder = row.get('textbook_wasabi_folder', '').strip()
                        
                        if textbook_name:
                            # 教材が存在するかチェック
                            cur.execute('SELECT id FROM social_studies_textbooks WHERE name = %s', (textbook_name,))
                            existing_textbook = cur.fetchone()
                            
                            if existing_textbook:
                                textbook_id = existing_textbook[0]
                            else:
                                # 新しい教材を作成
                                subject = row.get('subject', '').strip() or default_subject
                                if not subject:
                                    app.logger.warning(f"行{row_num}: 科目が指定されていません")
                                    skipped_count += 1
                                    continue
                                
                                cur.execute('''
                                    INSERT INTO social_studies_textbooks 
                                    (name, subject, grade, publisher, wasabi_folder_path)
                                    VALUES (%s, %s, %s, %s, %s)
                                    RETURNING id
                                ''', (textbook_name, subject, textbook_grade, textbook_publisher, 
                                     textbook_wasabi_folder or 'question_images'))
                                textbook_id = cur.fetchone()[0]
                                app.logger.info(f"行{row_num}: 新しい教材を作成しました - ID: {textbook_id}")
                        else:
                            # 従来の教材ID指定方式
                            csv_textbook_id = row.get('textbook_id', '').strip()
                            if csv_textbook_id:
                                try:
                                    textbook_id = int(csv_textbook_id)
                                    # 教材IDが存在するかチェック
                                    cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                                    if not cur.fetchone():
                                        textbook_id = None
                                except ValueError:
                                    textbook_id = None
                            elif default_textbook_id:
                                try:
                                    textbook_id = int(default_textbook_id)
                                    # 教材IDが存在するかチェック
                                    cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                                    if not cur.fetchone():
                                        textbook_id = None
                                except ValueError:
                                    textbook_id = None
                        
                        # 単元情報の処理
                        unit_id = None
                        unit_name = row.get('unit_name', '').strip()
                        unit_chapter = row.get('unit_chapter', '').strip()
                        
                        if unit_name and textbook_id:
                    # 単元が存在するかチェック
                            cur.execute('SELECT id FROM social_studies_units WHERE name = %s AND textbook_id = %s', 
                                       (unit_name, textbook_id))
                            existing_unit = cur.fetchone()
                            
                            if existing_unit:
                                unit_id = existing_unit[0]
                            else:
                                # 新しい単元を作成
                                chapter_number = None
                                if unit_chapter:
                                    try:
                                        chapter_number = int(unit_chapter)
                                    except ValueError:
                                        app.logger.warning(f"行{row_num}: 無効な章番号 '{unit_chapter}'")
                                
                                cur.execute('''
                                    INSERT INTO social_studies_units 
                                    (textbook_id, name, chapter_number)
                                    VALUES (%s, %s, %s)
                                    RETURNING id
                                ''', (textbook_id, unit_name, chapter_number))
                                unit_id = cur.fetchone()[0]
                                app.logger.info(f"行{row_num}: 新しい単元を作成しました - ID: {unit_id}")
                        else:
                            # 従来の単元ID指定方式
                            csv_unit_id = row.get('unit_id', '').strip()
                            if csv_unit_id:
                                try:
                                    unit_id = int(csv_unit_id)
                                    # 単元IDが存在するかチェック
                                    cur.execute('SELECT id FROM social_studies_units WHERE id = %s', (unit_id,))
                                    if not cur.fetchone():
                                        unit_id = None
                                except ValueError:
                                    unit_id = None
                        
                        # 画像URLと画像タイトルの処理
                        image_url = row.get('image_url', '').strip()
                        image_title = row.get('image_title', '').strip()
                        
                        # 従来のimage_name項目も対応（後方互換性）
                        image_name = row.get('image_name', '').strip()
                        if not image_url and image_name and textbook_id:
                            # 画像存在確認とURL取得
                            try:
                                # 教材のフォルダパスを取得
                                cur.execute('SELECT wasabi_folder_path FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                                result = cur.fetchone()
                                if result and result[0]:
                                    folder_path = result[0]
                                    
                                    # Wasabiで画像を検索
                                    s3_client = init_wasabi_client()
                                    if s3_client:
                                        bucket_name = os.getenv('WASABI_BUCKET')
                                        endpoint = os.getenv('WASABI_ENDPOINT')
                                        
                                        # 複数の拡張子で試行
                                        extensions = ['jpg', 'jpeg', 'png', 'gif']
                                        for ext in extensions:
                                            try:
                                                image_key = f"{folder_path}/{image_name}.{ext}"
                                                s3_client.head_object(Bucket=bucket_name, Key=image_key)
                                                image_url = f"{endpoint}/{bucket_name}/{image_key}"
                                                break
                                            except Exception:
                                                continue
                            except Exception as e:
                                app.logger.warning(f"行{row_num}: 画像URL取得エラー: {e}")
                        
                        # 重複チェック（同じ問題文と正解の組み合わせ）
                        try:
                            cur.execute('''
                                SELECT id FROM social_studies_questions 
                                WHERE question = %s AND correct_answer = %s
                            ''', (question, correct_answer))
                            if cur.fetchone():
                                app.logger.warning(f"行{row_num}: 重複データ - question: '{question}', correct_answer: '{correct_answer}'")
                                skipped_count += 1
                                continue
                            # 問題を登録
                            cur.execute('''
                                INSERT INTO social_studies_questions 
                                (subject, textbook_id, unit_id, question, correct_answer, acceptable_answers, explanation, answer_suffix, image_url, image_title)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''', (subject, textbook_id, unit_id, question, correct_answer, acceptable_answers, explanation, answer_suffix, image_url, image_title))
                            app.logger.info(f"行{row_num}: 問題を登録しました - subject: '{subject}', question: '{question}'")
                            registered_count += 1
                        except Exception as e:
                            app.logger.error(f"行{row_num}処理エラー: {e}, データ: {row}")
                            skipped_count += 1
                            continue
                        
                    except Exception as e:
                        app.logger.error(f"行{row_num}処理エラー: {e}, データ: {row}")
                        skipped_count += 1
                        continue
                
                conn.commit()
                
                app.logger.info(f"CSVアップロード完了: 登録{registered_count}件, スキップ{skipped_count}件")
                
                return jsonify({
                    'success': True, 
                    'message': f'{registered_count}件の問題を登録しました',
                    'registered_count': registered_count,
                    'skipped_count': skipped_count
                })
                
    except Exception as e:
        app.logger.error(f"CSVアップロードエラー: {e}")
        return jsonify({'error': f'CSVアップロードに失敗しました: {str(e)}'}), 500

@app.route('/social_studies/admin/upload_image/<int:question_id>', methods=['POST'])
@login_required
def social_studies_upload_image(question_id):
    """問題に関連する画像をアップロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        print(f"🔍 画像アップロードリクエスト受信: question_id={question_id}")
        print(f"🔍 リクエストファイル: {list(request.files.keys())}")
        
        if 'image' not in request.files:
            return jsonify({'error': '画像ファイルが選択されていません'}), 400
        
        image_file = request.files['image']
        print(f"🔍 画像ファイル: {image_file.filename}, サイズ: {image_file.content_length if hasattr(image_file, 'content_length') else 'Unknown'}")
        
        if image_file.filename == '':
            return jsonify({'error': '画像ファイルが選択されていません'}), 400
        
        # 問題と教材IDを取得
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id, textbook_id FROM social_studies_questions WHERE id = %s', (question_id,))
                result = cur.fetchone()
                if not result:
                    return jsonify({'error': '指定された問題が見つかりません'}), 404
                
                textbook_id = result[1]
        
        # 画像をWasabiにアップロード
        print(f"🔍 Wasabiアップロード開始: question_id={question_id}, textbook_id={textbook_id}")
        image_url, error = upload_image_to_wasabi(image_file, question_id, textbook_id)
        
        if error:
            print(f"❌ Wasabiアップロードエラー: {error}")
            return jsonify({'error': error}), 500
        
        # データベースに画像URLを保存
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE social_studies_questions 
                    SET image_url = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                ''', (image_url, question_id))
                conn.commit()
                
        return jsonify({
            'success': True, 
            'message': '画像をアップロードしました',
            'image_url': image_url
        })
        
    except Exception as e:
        app.logger.error(f"画像アップロードエラー: {e}")
        return jsonify({'error': f'画像アップロードに失敗しました: {str(e)}'}), 500

@app.route('/social_studies/admin/delete_image/<int:question_id>', methods=['POST'])
@login_required
def social_studies_delete_image(question_id):
    """問題に関連する画像を削除（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # 現在の画像URLを取得
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT image_url FROM social_studies_questions WHERE id = %s', (question_id,))
                result = cur.fetchone()
                if not result:
                    return jsonify({'error': '指定された問題が見つかりません'}), 404
                
                current_image_url = result[0]
                if not current_image_url:
                    return jsonify({'error': 'この問題には画像が設定されていません'}), 400
        
        # Wasabiから画像を削除
        if current_image_url:
            try:
                s3_client = init_wasabi_client()
                if s3_client:
                    # URLからファイルパスを抽出
                    bucket_name = os.getenv('WASABI_BUCKET')
                    endpoint = os.getenv('WASABI_ENDPOINT')
                    if endpoint.endswith('/'):
                        endpoint = endpoint[:-1]
                    
                    file_path = current_image_url.replace(f"{endpoint}/{bucket_name}/", "")
                    s3_client.delete_object(Bucket=bucket_name, Key=file_path)
            except Exception as e:
                app.logger.warning(f"Wasabiからの画像削除に失敗: {e}")
        
        # データベースから画像URLと画像タイトルを削除
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE social_studies_questions 
                    SET image_url = NULL, image_title = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (question_id,))
                conn.commit()
                
        return jsonify({
            'success': True, 
            'message': '画像を削除しました'
        })
                
    except Exception as e:
        app.logger.error(f"画像削除エラー: {e}")
        return jsonify({'error': f'画像削除に失敗しました: {str(e)}'}), 500

@app.route('/social_studies/admin/question/<int:question_id>')
@login_required
def social_studies_get_question(question_id):
    """問題詳細を取得（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT id, subject, question, correct_answer, acceptable_answers, 
                           explanation, image_url, image_title, difficulty_level, textbook_id, unit_id
                    FROM social_studies_questions 
                    WHERE id = %s
                ''', (question_id,))
                
                question = cur.fetchone()
                if not question:
                    return jsonify({'error': '問題が見つかりません'}), 404
                
                return jsonify({
                    'success': True,
                    'question': dict(question)
                })
                
    except Exception as e:
        app.logger.error(f"問題取得エラー: {e}")
        return jsonify({'error': f'問題の取得に失敗しました: {str(e)}'}), 500

# ========== CSVダウンロード機能 ==========

@app.route('/social_studies/admin/download_csv_template', methods=['GET'])
@login_required
def social_studies_download_csv_template():
    """教材・単元・フォルダパスが入力されたCSVテンプレートをダウンロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # CSVデータを作成
        csv_data = []
        
        # ヘッダー行（1行目）
        csv_data.append([
            'subject', 'textbook_id', 'textbook_name', 'textbook_grade', 'textbook_publisher', 
            'textbook_wasabi_folder', 'unit_id', 'unit_name', 'unit_chapter', 
            'question', 'correct_answer', 'acceptable_answers', 'answer_suffix', 'explanation', 'image_url', 'image_title'
        ])
        
        # 入力例行（2行目、コメントアウト）
        csv_data.append([
            '# 地理',  # 科目
            '# ',  # 教材ID
            '# 新しい教材名',  # 教材名
            '# 中学1年',  # 学年
            '# 出版社名',  # 出版社
            '# 社会/新しい教材/地理',  # Wasabiフォルダパス
            '# ',  # 単元ID
            '# 新しい単元名',  # 単元名
            '# 1',  # 章番号
            '# 新しい問題文',  # 問題文
            '# 新しい正解',  # 正解
            '# 新しい許容回答1,新しい許容回答2',  # 許容回答
            '# 新しい解答欄の補足',  # 解答欄の補足
            '# 新しい解説',  # 解説
            '# https://s3.ap-northeast-1.wasabisys.com/so-image/social studies/geography/',  # 画像URL
            '# 1-1.jpg'  # 画像タイトル
        ])
        
        # 基本画像URL
        base_image_url = f"https://s3.ap-northeast-1.wasabisys.com/{os.getenv('WASABI_BUCKET')}/question_images"
        
        # 実際のテンプレート行を追加
        csv_data.append([
            '地理',  # 科目
            '',  # 教材ID
            '新しい教材名',  # 教材名
            '中学1年',  # 学年
            '出版社名',  # 出版社
            '社会/新しい教材/地理',  # Wasabiフォルダパス
            '',  # 単元ID
            '新しい単元名',  # 単元名
            '1',  # 章番号
            '新しい問題文',  # 問題文
            '新しい正解',  # 正解
            '新しい許容回答1,新しい許容回答2',  # 許容回答
            '新しい解答欄の補足',  # 解答欄の補足
            '新しい解説',  # 解説
            f"{base_image_url}/",  # 画像URL（ベースURLのみ）
            '1-1.jpg'  # 画像タイトル
        ])
        
        # 追加のテンプレート行
        csv_data.append([
            '歴史',  # 科目
            '',  # 教材ID
            '',  # 教材名
            '',  # 学年
            '',  # 出版社
            '',  # Wasabiフォルダパス
            '',  # 単元ID
            '',  # 単元名
            '2',  # 章番号
            '',  # 問題文
            '',  # 正解
            '',  # 許容回答
            '',  # 解答欄の補足
            '',  # 解説
            f"{base_image_url}/",  # 画像URL（ベースURLのみ）
            '2-1.jpg'  # 画像タイトル
        ])
        
        # CSVファイルを生成（BOM付きUTF-8）
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_data)
        
        # BOM付きUTF-8でエンコード
        csv_content = output.getvalue()
        csv_bytes = csv_content.encode('utf-8-sig')  # BOM付きUTF-8
        
        # ファイル名を設定
        filename = 'social_studies_template.csv'
        
        # レスポンスを作成
        response = app.response_class(
            response=csv_bytes,
            status=200,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"CSVテンプレートダウンロードエラー: {e}")
        return jsonify({'error': 'CSVテンプレートの生成に失敗しました'}), 500

@app.route('/social_studies/admin/download_units_csv/<int:textbook_id>', methods=['GET'])
@login_required
def download_units_csv(textbook_id):
    """指定された教材の単元一覧をCSVでダウンロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # CSVデータを作成
        csv_data = []
        
        # 既存の単元データを取得
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT name, chapter_number, description
                    FROM social_studies_units
                    WHERE textbook_id = %s
                    ORDER BY chapter_number, id
                ''', (textbook_id,))
                existing_units = cur.fetchall()
        
        # ヘッダー行（1行目）
        csv_data.append(['章番号', '単元名', '説明'])
        
        # 既存の単元データを追加（2行目以降）
        for unit in existing_units:
            csv_data.append([
                str(unit['chapter_number']) if unit['chapter_number'] else '',  # 章番号
                unit['name'] or '',  # 単元名
                unit['description'] or ''  # 説明
            ])
        
        # 新しい単元追加用の空行を追加（既存単元の後）
        for i in range(1, 6):  # 5行分の空行を追加
            csv_data.append(['', '', ''])
        
        # CSVファイルを生成（BOM付きUTF-8）
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_data)
        
        # BOM付きUTF-8でエンコード
        csv_content = output.getvalue()
        csv_bytes = csv_content.encode('utf-8-sig')  # BOM付きUTF-8
        
        # ファイル名を完全に安全な形式に制限
        filename = f"textbook_{textbook_id}_units_template.csv"
        
        # レスポンスを作成
        response = app.response_class(
            response=csv_bytes,
            status=200,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"単元CSVダウンロードエラー: {e}")
        return jsonify({'error': '単元CSVの生成に失敗しました'}), 500

@app.route('/social_studies/admin/download_questions_csv/<int:textbook_id>', methods=['GET'])
@login_required
def download_questions_csv(textbook_id):
    """指定された教材の問題一覧をCSVでダウンロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # CSVデータを作成
        csv_data = []
        
        # ヘッダー行（1行目）
        csv_data.append([
            '章番号', '単元名', '問題文', '正解', '許容回答', '解答欄の補足', 
            '解説', '難易度', '画像URL', '画像タイトル', '登録日'
        ])
        

        
        # 教材の画像URLを取得
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT wasabi_folder_path
                    FROM social_studies_textbooks 
                    WHERE id = %s
                ''', (textbook_id,))
                textbook = cur.fetchone()
                base_image_url = f"https://s3.ap-northeast-1.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{textbook['wasabi_folder_path'] or 'question_images'}" if textbook else "https://s3.ap-northeast-1.wasabisys.com/bucket/question_images"
        
        # 既存の問題データを取得
        cur.execute('''
            SELECT u.name as unit_name, u.chapter_number, q.question, q.correct_answer, 
                   q.acceptable_answers, q.answer_suffix, q.explanation, q.difficulty_level, 
                   q.image_url, q.image_title, q.created_at
                    FROM social_studies_questions q
            JOIN social_studies_units u ON q.unit_id = u.id
            WHERE q.textbook_id = %s
            ORDER BY u.chapter_number, q.question_number, q.id
        ''', (textbook_id,))
        existing_questions = cur.fetchall()
        
        # 既存の問題データを追加（2行目以降）
        for question in existing_questions:
            csv_data.append([
                str(question['chapter_number']) if question['chapter_number'] else '',  # 章番号
                question['unit_name'] or '',  # 単元名
                question['question'] or '',  # 問題文
                question['correct_answer'] or '',  # 正解
                question['acceptable_answers'] or '',  # 許容回答
                question['answer_suffix'] or '',  # 解答欄の補足
                question['explanation'] or '',  # 解説
                question['difficulty_level'] or '基本',  # 難易度
                question['image_url'] or '',  # 画像URL
                question['image_title'] or '',  # 画像タイトル
                question['created_at'].strftime('%Y-%m-%d') if question['created_at'] else ''  # 登録日
            ])
        
        # 新しい問題追加用の空行を追加（既存問題の後）
        for i in range(1, 6):  # 5行分の空行を追加
            csv_data.append(['', '', '', '', '', '', '', '', '', '', ''])
        
        # CSVファイルを生成（BOM付きUTF-8）
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_data)
        
        # BOM付きUTF-8でエンコード
        csv_content = output.getvalue()
        csv_bytes = csv_content.encode('utf-8-sig')  # BOM付きUTF-8
        
        # ファイル名を完全に安全な形式に制限
        filename = f"textbook_{textbook_id}_questions_template.csv"
        
        # レスポンスを作成
        response = app.response_class(
            response=csv_bytes,
            status=200,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"問題CSVダウンロードエラー: {e}")
        return jsonify({'error': '問題CSVの生成に失敗しました'}), 500

@app.route('/social_studies/admin/download_unit_questions_csv/<int:textbook_id>/<int:unit_id>', methods=['GET'])
@login_required
def download_unit_questions_csv(textbook_id, unit_id):
    """指定された単元の問題一覧をCSVでダウンロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        # CSVデータを作成
        csv_data = []
        
        # ヘッダー行（1行目）
        csv_data.append([
            '章番号', '問題番号', '教材名', '単元名', '問題文', '正解', '許容回答', '解答欄の補足', '解説', '難易度', '画像URL', '画像タイトル'
        ])
        
        # 教材と単元の情報を取得
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 教材と単元の情報を取得
                cur.execute('''
                    SELECT t.name as textbook_name, t.wasabi_folder_path, u.name as unit_name, u.chapter_number
                    FROM social_studies_textbooks t
                    JOIN social_studies_units u ON t.id = u.textbook_id
                    WHERE t.id = %s AND u.id = %s
                ''', (textbook_id, unit_id))
                result = cur.fetchone()
                
                if not result:
                    return jsonify({'error': '教材または単元が見つかりません'}), 404
                
                textbook_name = result['textbook_name']
                unit_name = result['unit_name']
                chapter_number = result['chapter_number'] or 1
                base_image_url = f"https://s3.ap-northeast-1-ntt.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{result['wasabi_folder_path']}/{chapter_number}"
                

                
                # 既存の問題データを取得
                cur.execute('''
                    SELECT id, question_number, question, correct_answer, acceptable_answers, answer_suffix, 
                           explanation, difficulty_level, image_url, image_title
                    FROM social_studies_questions
                    WHERE textbook_id = %s AND unit_id = %s
                    ORDER BY question_number, id
                ''', (textbook_id, unit_id))
                existing_questions = cur.fetchall()
        
        # 既存の問題データを追加（3行目以降）
        for question in existing_questions:
            # 画像URLとタイトルを分離
            image_url_without_number = base_image_url  # 問題番号を含まないURL
            image_title_from_url = ''
            
            if question['question_number']:
                # 問題番号がある場合は、タイトルとして使用
                image_title_from_url = str(question['question_number'])
            elif question['image_url']:
                # 既存の画像URLがある場合は、そのURLからファイル名を抽出
                image_url_parts = question['image_url'].split('/')
                if len(image_url_parts) > 0:
                    image_title_from_url = image_url_parts[-1]
            
            csv_data.append([
                str(chapter_number),  # 章番号
                str(question['question_number'] or question['id']),  # 問題番号（単元内番号、なければID）
                textbook_name,  # 教材名
                unit_name,      # 単元名
                question['question'] or '',  # 問題文
                question['correct_answer'] or '',  # 正解
                question['acceptable_answers'] or '',  # 許容回答
                question['answer_suffix'] or '',  # 解答欄の補足
                question['explanation'] or '',  # 解説
                question['difficulty_level'] or '基本',  # 難易度
                image_url_without_number,  # 問題番号を含まないWasabi URL
                image_title_from_url  # 問題番号またはファイル名
            ])
        
        # 新しい問題追加用の空行を追加（既存問題の後）
        for i in range(1, 11):  # 10行分の空行を追加
            csv_data.append([
                '', '', '', '', '', '', '', '', '', '', '', ''
            ])
        
        # CSVファイルを生成（BOM付きUTF-8）
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_data)
        
        # BOM付きUTF-8でエンコード
        csv_content = output.getvalue()
        csv_bytes = csv_content.encode('utf-8-sig')  # BOM付きUTF-8
        
        # ファイル名を完全に安全な形式に制限
        filename = f"unit_{unit_id}_questions_template.csv"
        
        # レスポンスを作成
        response = app.response_class(
            response=csv_bytes,
            status=200,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"単元問題CSVダウンロードエラー: {e}")
        app.logger.error(f"エラーの詳細: {type(e).__name__}")
        import traceback
        app.logger.error(f"トレースバック: {traceback.format_exc()}")
        return jsonify({'error': f'単元問題CSVの生成に失敗しました: {str(e)}'}), 500

@app.route('/social_studies/admin/upload_unit_questions_csv', methods=['POST'])
@login_required
def social_studies_upload_unit_questions_csv():
    """単元ごとの問題CSV一括登録（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        textbook_id = request.form.get('textbook_id', '').strip()
        unit_id = request.form.get('unit_id', '').strip()
        
        if not textbook_id or not unit_id:
            return jsonify({'error': '教材IDと単元IDが必要です'}), 400
        
        try:
            textbook_id = int(textbook_id)
            unit_id = int(unit_id)
        except ValueError:
            return jsonify({'error': '無効な教材IDまたは単元IDです'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'CSVファイルを選択してください'}), 400
        
        # CSVファイルを読み込み（複数エンコーディング対応）
        file_content = file.read()
        csv_data = None
        
        # 複数のエンコーディングを試行
        encodings = ['utf-8-sig', 'utf-8', 'shift_jis', 'cp932', 'euc-jp', 'iso-2022-jp']
        for encoding in encodings:
            try:
                csv_data = file_content.decode(encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue
        
        if csv_data is None:
            return jsonify({'error': 'CSVファイルのエンコーディングを認識できませんでした。UTF-8、Shift_JIS、CP932、EUC-JP、ISO-2022-JPのいずれかで保存してください。'}), 400
        
        if len(csv_data) < 2:  # ヘッダー行 + データ行が最低1行必要
            return jsonify({'error': 'CSVファイルにデータが含まれていません'}), 400
        
        if len(csv_data) > 1001:  # ヘッダー行 + 最大1000行
            return jsonify({'error': 'CSVファイルは最大1000行までです'}), 400
        
        # 教材と単元が存在するかチェック
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                if not cur.fetchone():
                    return jsonify({'error': '指定された教材が見つかりません'}), 404
                
                cur.execute('SELECT id FROM social_studies_units WHERE id = %s AND textbook_id = %s', (unit_id, textbook_id))
                if not cur.fetchone():
                    return jsonify({'error': '指定された単元が見つかりません'}), 404
        
        reader = csv.DictReader(csv_data)
        registered_count = 0
        skipped_count = 0
        
        app.logger.info(f"単元問題CSVアップロード開始: 教材{textbook_id}, 単元{unit_id}, {len(csv_data)}行のデータ")
        app.logger.info(f"CSVデータの最初の5行: {csv_data[:5]}")
        app.logger.info(f"CSVヘッダー: {reader.fieldnames}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for row_num, row in enumerate(reader, 1):
                    app.logger.info(f"行{row_num}を処理中: {row}")
                    try:
                        # コメント行をスキップ
                        question = row.get('問題文', '').strip()
                        if question.startswith('#') or not question:
                            app.logger.info(f"行{row_num}: コメント行または空行をスキップ")
                            continue
                        
                        correct_answer = row.get('正解', '').strip()
                        
                        # バリデーション
                        if not question or not correct_answer:
                            app.logger.warning(f"行{row_num}: 必須フィールドが不足 - question: '{question}', correct_answer: '{correct_answer}'")
                            skipped_count += 1
                            continue
                        
                        # 問題番号の取得
                        question_number = row.get('問題番号', '').strip()
                        
                        # 教材名と単元名の取得（オプション）
                        csv_textbook_name = row.get('教材名', '').strip()
                        csv_unit_name = row.get('単元名', '').strip()
                        
                        # オプションフィールドの取得（日本語ヘッダー対応）
                        acceptable_answers = row.get('許容回答', '').strip()
                        explanation = row.get('解説', '').strip()
                        answer_suffix = row.get('解答欄の補足', '').strip()
                        difficulty_level = row.get('難易度', '').strip()
                        image_url_base = row.get('画像URL', '').strip()
                        image_title = row.get('画像タイトル', '').strip()
                        
                        # 画像URLとタイトルを結合して完全なURLを生成
                        image_url = ''
                        if image_url_base and image_title:
                            image_url = f"{image_url_base}/{image_title}"
                        elif image_url_base:
                            image_url = image_url_base
                        
                        app.logger.info(f"行{row_num}の画像処理: image_url_base='{image_url_base}', image_title='{image_title}', 結合後image_url='{image_url}'")
                        
                        # 問題番号が指定されている場合は、その番号で既存の問題を検索
                        if question_number and question_number.isdigit():
                            q_number = int(question_number)
                            cur.execute('''
                                SELECT id FROM social_studies_questions 
                                WHERE question_number = %s AND textbook_id = %s AND unit_id = %s
                            ''', (q_number, textbook_id, unit_id))
                            existing_question = cur.fetchone()
                            
                            if existing_question:
                                # 既存の問題を上書き
                                app.logger.info(f"行{row_num}: 問題番号{q_number}の既存問題を上書きします - {question}")
                                app.logger.info(f"行{row_num}: 保存する値 - image_url='{image_url}', image_title='{image_title}'")
                                cur.execute('''
                                    UPDATE social_studies_questions 
                                    SET question = %s, correct_answer = %s, acceptable_answers = %s, 
                                        answer_suffix = %s, explanation = %s, difficulty_level = %s, 
                                        image_url = %s, image_title = %s
                                    WHERE id = %s
                                ''', (question, correct_answer, acceptable_answers, answer_suffix, 
                                      explanation, difficulty_level, image_url, image_title, existing_question[0]))
                                registered_count += 1
                            else:
                                # 問題番号が存在しない場合は新規登録
                                app.logger.info(f"行{row_num}: 問題番号{q_number}で新規問題を登録します - {question}")
                                app.logger.info(f"行{row_num}: 保存する値 - image_url='{image_url}', image_title='{image_title}'")
                                cur.execute('''
                                    INSERT INTO social_studies_questions 
                                    (textbook_id, unit_id, question_number, question, correct_answer, acceptable_answers, 
                                     answer_suffix, explanation, difficulty_level, image_url, image_title)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ''', (textbook_id, unit_id, q_number, question, correct_answer, acceptable_answers,
                                      answer_suffix, explanation, difficulty_level, image_url, image_title))
                                registered_count += 1
                        else:
                            # 問題番号が指定されていない場合は、問題文と正解で既存の問題を検索
                            cur.execute('''
                                SELECT id FROM social_studies_questions 
                                WHERE question = %s AND correct_answer = %s AND textbook_id = %s AND unit_id = %s
                            ''', (question, correct_answer, textbook_id, unit_id))
                            existing_question = cur.fetchone()
                            
                            if existing_question:
                                # 既存の問題を上書き
                                app.logger.info(f"行{row_num}: 既存の問題を上書きします - {question}")
                                app.logger.info(f"行{row_num}: 保存する値 - image_url='{image_url}', image_title='{image_title}'")
                                cur.execute('''
                                    UPDATE social_studies_questions 
                                    SET acceptable_answers = %s, answer_suffix = %s, explanation = %s, 
                                        difficulty_level = %s, image_url = %s, image_title = %s
                                    WHERE id = %s
                                ''', (acceptable_answers, answer_suffix, explanation, difficulty_level, 
                                      image_url, image_title, existing_question[0]))
                                registered_count += 1
                            else:
                                # 新しい問題を登録（問題番号を自動採番）
                                cur.execute('''
                                    SELECT COALESCE(MAX(question_number), 0) + 1
                                    FROM social_studies_questions
                                    WHERE textbook_id = %s AND unit_id = %s
                                ''', (textbook_id, unit_id))
                                next_number = cur.fetchone()[0]
                                
                                app.logger.info(f"行{row_num}: 新規問題を登録します（問題番号自動採番: {next_number}） - {question}")
                                app.logger.info(f"行{row_num}: 保存する値 - image_url='{image_url}', image_title='{image_title}'")
                                cur.execute('''
                                    INSERT INTO social_studies_questions 
                                    (textbook_id, unit_id, question_number, question, correct_answer, acceptable_answers, 
                                     answer_suffix, explanation, difficulty_level, image_url, image_title)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ''', (textbook_id, unit_id, next_number, question, correct_answer, acceptable_answers,
                                      answer_suffix, explanation, difficulty_level, image_url, image_title))
                                registered_count += 1
                        app.logger.info(f"行{row_num}: 問題登録完了")
                        
                    except Exception as e:
                        app.logger.error(f"行{row_num}の処理でエラー: {e}")
                        skipped_count += 1
                        continue
                
                conn.commit()
        
        app.logger.info(f"単元問題CSVアップロード完了: 登録{registered_count}件, スキップ{skipped_count}件")
        
        return jsonify({
            'success': True,
            'message': '単元問題CSVアップロードが完了しました',
            'registered_count': registered_count,
            'skipped_count': skipped_count
        })
        
    except Exception as e:
        app.logger.error(f"単元問題CSVアップロードエラー: {e}")
        return jsonify({'error': f'単元問題CSVアップロードに失敗しました: {str(e)}'}), 500

@app.route('/social_studies/admin/unit_questions/<int:textbook_id>/<int:unit_id>')
@login_required
def social_studies_admin_unit_questions(textbook_id, unit_id):
    """単元ごとの問題一覧（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('admin'))
    
    textbook_info = None
    unit_info = None
    questions = []
    image_path_info = None
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 教材情報取得
                cur.execute('SELECT id, name, wasabi_folder_path FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                textbook_info = cur.fetchone()
                # 単元情報取得
                cur.execute('SELECT id, name, chapter_number FROM social_studies_units WHERE id = %s AND textbook_id = %s', (unit_id, textbook_id))
                unit_info = cur.fetchone()
                # 問題リスト取得
                cur.execute('''
                    SELECT * FROM social_studies_questions
                    WHERE textbook_id = %s AND unit_id = %s
                    ORDER BY question_number, id
                ''', (textbook_id, unit_id))
                questions = cur.fetchall()
                
                # 画像パス情報を生成
                if textbook_info and unit_info:
                    chapter_number = unit_info['chapter_number'] or 1
                    base_image_url = f"https://s3.ap-northeast-1-ntt.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{textbook_info['wasabi_folder_path']}/{chapter_number}"
                    
                    # この単元に画像が設定されている問題数を取得
                    cur.execute('''
                        SELECT COUNT(*) as count
                        FROM social_studies_questions
                        WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
                    ''', (textbook_id, unit_id))
                    image_questions_count = cur.fetchone()['count']
                    
                    image_path_info = {
                        'base_url': base_image_url,
                        'chapter_number': chapter_number,
                        'wasabi_folder_path': textbook_info['wasabi_folder_path'],
                        'image_questions_count': image_questions_count
                    }
    except Exception as e:
        app.logger.error(f"単元ごとの問題一覧取得エラー: {e}")
        flash('単元ごとの問題一覧の取得に失敗しました', 'error')
    
    return render_template(
        'social_studies/admin_unit_questions.html',
        textbook_info=textbook_info,
        unit_info=unit_info,
        questions=questions,
        image_path_info=image_path_info
    )

@app.route('/social_studies/admin/update_image_path/<int:textbook_id>/<int:unit_id>', methods=['POST'])
@login_required
def update_unit_image_path(textbook_id, unit_id):
    """単元の画像URLを更新（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        data = request.get_json()
        new_image_url = data.get('image_url', '').strip()
        update_questions = data.get('update_questions', False)  # 問題の画像パスも更新するかどうか
        
        if not new_image_url:
            return jsonify({'error': '画像URLが必要です'}), 400
        
        if not new_image_url.startswith('https://'):
            return jsonify({'error': '有効なURLを入力してください（https://で始まる必要があります）'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 教材のWasabiフォルダパスを更新（URLからパスを抽出）
                # URLの形式: https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/path/to/folder
                url_parts = new_image_url.split('/')
                if len(url_parts) >= 6:
                    # so-image以降のパスを取得
                    bucket_index = url_parts.index('so-image') if 'so-image' in url_parts else -1
                    if bucket_index != -1 and bucket_index + 1 < len(url_parts):
                        folder_path = '/'.join(url_parts[bucket_index + 1:])
                        # 章番号を除いたパスを取得
                        path_parts = folder_path.split('/')
                        if len(path_parts) > 1:
                            # 最後の部分（章番号）を除く
                            wasabi_folder_path = '/'.join(path_parts[:-1])
                        else:
                            wasabi_folder_path = folder_path
                    else:
                        wasabi_folder_path = ''
                else:
                    wasabi_folder_path = ''
                
                # 教材のWasabiフォルダパスを更新
                cur.execute('''
                    UPDATE social_studies_textbooks 
                    SET wasabi_folder_path = %s 
                    WHERE id = %s
                ''', (wasabi_folder_path, textbook_id))
                
                # 問題の画像パスも更新する場合
                updated_questions_count = 0
                if update_questions:
                    # 単元に登録されている問題の画像URLを更新
                    cur.execute('''
                        SELECT id, image_url FROM social_studies_questions
                        WHERE textbook_id = %s AND unit_id = %s AND image_url IS NOT NULL AND image_url != ''
                    ''', (textbook_id, unit_id))
                    
                    questions = cur.fetchall()
                    for question_id, old_image_url in questions:
                        if old_image_url:
                            # 古いURLから画像ファイル名を抽出
                            old_url_parts = old_image_url.split('/')
                            if len(old_url_parts) > 0:
                                image_filename = old_url_parts[-1]  # 最後の部分がファイル名
                                # 新しいURLを構築
                                new_question_image_url = f"{new_image_url}/{image_filename}"
                                
                                # 問題の画像URLを更新
                                cur.execute('''
                                    UPDATE social_studies_questions 
                                    SET image_url = %s 
                                    WHERE id = %s
                                ''', (new_question_image_url, question_id))
                                updated_questions_count += 1
                
                conn.commit()
        
        message = '画像URLを更新しました'
        if update_questions and updated_questions_count > 0:
            message += f'（{updated_questions_count}件の問題の画像パスも更新しました）'
        
        return jsonify({
            'success': True,
            'message': message,
            'new_url': new_image_url,
            'new_path': wasabi_folder_path,
            'updated_questions_count': updated_questions_count
        })
        
    except Exception as e:
        app.logger.error(f"画像URL更新エラー: {e}")
        return jsonify({'error': f'画像URLの更新に失敗しました: {str(e)}'}), 500

# ユーザー管理機能は routes/admin.py に移動済み

if __name__ == '__main__':
    # データベース接続プールを初期化
    try:
        init_connection_pool()
        print("✅ データベース接続プール初期化完了")
        
        # データベース接続テスト
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    result = cur.fetchone()
                    print(f"✅ データベース接続テスト成功: {result}")
                    
                    # データベース最適化を実行
                    optimize_database_indexes()
                    print("✅ データベース最適化完了")
                    
        except Exception as e:
            print(f"❌ データベース接続テスト失敗: {e}")
            
    except Exception as e:
        print(f"❌ データベース接続プール初期化エラー: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)