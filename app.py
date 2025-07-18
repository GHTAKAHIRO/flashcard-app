# ========== Redis除去版 パート1: 基本設定・インポート・初期化 ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import math
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps
import json
import hashlib
import threading
import time
import queue
import psycopg2.pool
from contextlib import contextmanager
import atexit
from flask_wtf.csrf import CSRFProtect
import io
import csv
import re
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import uuid

# ========== 設定エリア ==========
load_dotenv(dotenv_path='dbname.env')

# 環境変数の確認とログ出力
print("🔍 環境変数チェック:")
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
    SEND_FILE_MAX_AGE_DEFAULT=31536000  # 1年
)

print("🚀 バックエンド高速化システム初期化完了")

# Flask-Login 初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    """Wasabi S3クライアントを初期化"""
    try:
        access_key = os.getenv('WASABI_ACCESS_KEY')
        secret_key = os.getenv('WASABI_SECRET_KEY')
        endpoint = os.getenv('WASABI_ENDPOINT')
        bucket_name = os.getenv('WASABI_BUCKET')
        
        print(f"🔍 Wasabi設定確認:")
        print(f"  ACCESS_KEY: {'Set' if access_key else 'Not Set'}")
        print(f"  SECRET_KEY: {'Set' if secret_key else 'Not Set'}")
        print(f"  ENDPOINT: {endpoint}")
        print(f"  BUCKET: {bucket_name}")
        
        if not all([access_key, secret_key, endpoint, bucket_name]):
            print("⚠️ Wasabi設定が不完全です。画像アップロード機能は無効になります。")
            return None
        
        print(f"🔍 Wasabi S3クライアント作成中...")
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name='ap-northeast-1'  # 日本リージョン
        )
        
        # 接続テスト
        print(f"🔍 Wasabiバケット接続テスト: {bucket_name}")
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print("✅ Wasabi S3クライアント初期化完了")
            return s3_client
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"❌ Wasabiバケット接続テスト失敗:")
            print(f"  エラーコード: {error_code}")
            print(f"  エラーメッセージ: {error_message}")
            if error_code == '403':
                print("  認証エラーまたは権限不足の可能性があります")
            elif error_code == '404':
                print("  バケットが存在しない可能性があります")
            return None
        
    except Exception as e:
        print(f"❌ Wasabi S3クライアント初期化エラー: {e}")
        print(f"❌ エラータイプ: {type(e).__name__}")
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
    """単元IDから章番号に基づいて画像フォルダパスを生成"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 単元情報を取得
                cur.execute('''
                    SELECT 
                        t.subject, 
                        u.chapter_number
                    FROM social_studies_units u
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = %s
                ''', (unit_id,))
                result = cur.fetchone()
                
                if result:
                    subject, chapter_number = result
                    
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
    """画像をWasabiにアップロード"""
    try:
        print(f"🔍 画像アップロード開始: question_id={question_id}, textbook_id={textbook_id}")
        
        s3_client = init_wasabi_client()
        if not s3_client:
            print("❌ Wasabiクライアント初期化失敗")
            return None, "Wasabi設定が不完全です"
        
        # 画像をPILで開いて検証
        image = Image.open(image_file)
        
        # 画像形式を確認
        if image.format not in ['JPEG', 'PNG', 'GIF']:
            return None, "サポートされていない画像形式です。JPEG、PNG、GIFのみ対応しています。"
        
        # ファイルサイズチェック（5MB以下）
        image_file.seek(0, 2)  # ファイルの末尾に移動
        file_size = image_file.tell()
        image_file.seek(0)  # ファイルの先頭に戻る
        
        if file_size > 5 * 1024 * 1024:  # 5MB
            return None, "ファイルサイズが大きすぎます。5MB以下にしてください。"
        
        # ユニークなファイル名を生成
        file_extension = image.format.lower()
        if file_extension == 'jpeg':
            file_extension = 'jpg'
        
        # 単元の章番号に基づいてフォルダパスを生成
        folder_path = get_unit_image_folder_path(question_id)
        print(f"🔍 使用するフォルダパス: {folder_path}")
        
        filename = f"{folder_path}/{question_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Wasabiにアップロード
        bucket_name = os.getenv('WASABI_BUCKET')
        s3_client.upload_fileobj(
            image_file,
            bucket_name,
            filename,
            ExtraArgs={
                'ContentType': f'image/{file_extension}',
                'ACL': 'public-read'
            }
        )
        
        # 公開URLを生成
        endpoint = os.getenv('WASABI_ENDPOINT')
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
        
        image_url = f"{endpoint}/{bucket_name}/{filename}"
        
        return image_url, None
        
    except ClientError as e:
        print(f"❌ Wasabi ClientError: {e}")
        return None, f"Wasabiアップロードエラー: {str(e)}"
    except Exception as e:
        print(f"❌ 画像アップロード例外: {e}")
        print(f"❌ 例外タイプ: {type(e).__name__}")
        return None, f"画像アップロードエラー: {str(e)}"

# DB接続情報
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
db_pool = None

def init_connection_pool():
    """データベース接続プールの初期化（最適化版）"""
    global db_pool
    try:
        # 本番環境では最小限の接続数に
        if os.environ.get('RENDER'):
            min_conn = 1
            max_conn = 3
        else:
            min_conn = 2
            max_conn = 10

        db_pool = psycopg2.pool.SimpleConnectionPool(
            min_conn,
            max_conn,
            host=os.environ.get('DB_HOST'),
            port=os.environ.get('DB_PORT'),
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD')
        )
        app.logger.info("🚀 データベース接続プール初期化完了")
    except Exception as e:
        app.logger.error(f"接続プール初期化エラー: {e}")
        raise

# 🔥 シンプルなインメモリキャッシュ（Redis代替）
memory_cache = {}
cache_timestamps = {}
cache_lock = threading.Lock()

print("📋 Redis除去版アプリ - 基本設定完了")

# ========== Redis除去版 パート2: データベース接続とインデックス最適化 ==========

@contextmanager
def get_db_connection():
    """プール化された接続を取得（最適化版）"""
    global db_pool
    if db_pool is None:
        try:
            init_connection_pool()
        except Exception as e:
            app.logger.error(f"接続プール初期化エラー: {e}")
            # フォールバック：直接接続
            pass
    
    conn = None
    try:
        if db_pool:  # 🔥 追加: プールが存在するかチェック
            try:
                conn = db_pool.getconn()
            except Exception as e:
                app.logger.error(f"プールから接続取得エラー: {e}")
                conn = None
        
        if conn:
            conn.autocommit = False
            yield conn
        else:
            # フォールバック：直接接続
            app.logger.warning("プール接続失敗、直接接続を試行")
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
        app.logger.error(f"DB接続エラー: {e}")
        app.logger.error(f"接続情報: host={DB_HOST}, port={DB_PORT}, dbname={DB_NAME}, user={DB_USER}")
        raise
    finally:
        if conn and db_pool:
            try:
                db_pool.putconn(conn)
            except Exception as e:
                app.logger.error(f"DB接続返却エラー: {e}")
                if conn:
                    conn.close()
        elif conn:
            conn.close()

def optimize_database_indexes():
    """🔥 データベースインデックス最適化（修正版）"""
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

class User(UserMixin):
    def __init__(self, id, username, password_hash, full_name, is_admin):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.full_name = full_name
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE id = %s", (user_id,))
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
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT COUNT(*) FROM study_log sl
                    JOIN image i ON sl.card_id = i.id
                    WHERE sl.user_id = %s AND i.source = %s
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
            with conn.cursor() as cur:
                # 最新のセッションで全問正解したかチェック
                cur.execute('''
                    SELECT vsl.session_id, COUNT(*) as total_words,
                           SUM(CASE WHEN vsl.result = 'known' THEN 1 ELSE 0 END) as correct_words
                    FROM vocabulary_study_log vsl
                    WHERE vsl.user_id = %s AND vsl.source = %s 
                    AND vsl.chapter_id = %s AND vsl.chunk_number = %s
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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 基本の進捗情報を取得
                cur.execute('''
                    SELECT is_completed, is_passed, completed_at, passed_at
                    FROM vocabulary_chunk_progress
                    WHERE user_id = %s AND source = %s AND chapter_id = %s AND chunk_number = %s
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                # 正解数を取得
                cur.execute('''
                    SELECT COUNT(*) as correct_count
                    FROM vocabulary_study_log
                    WHERE user_id = %s AND source = %s AND chapter_id = %s AND chunk_number = %s AND result = 'known'
                ''', (user_id, source, chapter_id, chunk_number))
                correct_result = cur.fetchone()
                correct_count = correct_result['correct_count'] if correct_result else 0
                
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.pop('_flashes', None)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE username = %s", (username,))
                    user = cur.fetchone()

            if user and check_password_hash(user[2], password):
                login_user(User(user[0], user[1], user[2], user[3], user[4]))
                # 最終ログイン時刻を更新
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user[0],))
                        conn.commit()
                # 管理者の場合は管理者画面にリダイレクト
                if user[4]:  # is_adminがTrueの場合
                    return redirect(url_for('admin'))
                # 通常ユーザーの場合はnextパラメータまたはダッシュボードにリダイレクト
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash("ログインに失敗しました。")
        except Exception as e:
            app.logger.error(f"ログインエラー: {e}")
            flash("ログイン中にエラーが発生しました")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password))
                    conn.commit()
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"登録エラー: {e}")

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE username = %s", (username,))
                        user = cur.fetchone()

                if user and check_password_hash(user[2], password):
                    login_user(User(user[0], user[1], user[2], user[3], user[4]))
                    # 最終ログイン時刻を更新
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user[0],))
                            conn.commit()
                    # 管理者の場合は管理者画面にリダイレクト
                    if user[4]:  # is_adminがTrueの場合
                        return redirect(url_for('admin'))
                    # 通常ユーザーの場合はnextパラメータまたは管理画面にリダイレクト
                    next_page = request.args.get('next')
                    if next_page:
                        return redirect(next_page)
                    return redirect(url_for('admin'))
                else:
                    flash("ログインに失敗しました。")
            except Exception as e:
                app.logger.error(f"ログインエラー: {e}")
                flash("ログイン中にエラーが発生しました")
    
    if current_user.is_authenticated:
        # 管理者の場合は管理者画面にリダイレクト
        if current_user.is_admin:
            return redirect(url_for('admin'))
        return redirect(url_for('admin'))
    return render_template('login.html')

# favicon.icoのルートを追加
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/dashboard')
@login_required
def dashboard():
    """ダッシュボード画面 - 管理画面にリダイレクト"""
    return redirect(url_for('admin'))

@app.route('/set_page_range_and_prepare/<source>', methods=['POST'])
@login_required
def set_page_range_and_prepare(source):
    """ダッシュボードからの設定保存＆準備画面遷移（学習開始後は変更不可）"""
    user_id = str(current_user.id)
    
    # 学習履歴があるかチェック
    if has_study_history(user_id, source):
        flash("⚠️ 学習開始後は設定変更できません。現在の設定で学習を継続してください。")
        return redirect(url_for('prepare', source=source))
    
    page_range = request.form.get('page_range', '').strip()
    difficulty_list = request.form.getlist('difficulty')
    difficulty = ','.join(difficulty_list) if difficulty_list else ''
    
    # デバッグ用ログ出力
    app.logger.info(f"[DEBUG] page_range: '{page_range}', difficulty: '{difficulty}'")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO user_settings (user_id, source, page_range, difficulty)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, source)
                    DO UPDATE SET page_range = EXCLUDED.page_range, difficulty = EXCLUDED.difficulty
                ''', (user_id, source, page_range, difficulty))
                conn.commit()
        
        # キャッシュクリア（設定変更時）
        clear_user_cache(user_id, source)
        
        flash("✅ 設定を保存しました。")
    except Exception as e:
        app.logger.error(f"user_settings保存エラー: {e}")
        flash("❌ 設定の保存に失敗しました")
    
    return redirect(url_for('prepare', source=source))

@app.route('/reset_history/<source>', methods=['POST'])
@login_required
def reset_history(source):
    try:
        app.logger.info(f"履歴リセット開始: user_id={current_user.id}, source={source}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # まず、study_logテーブルの構造を確認
                try:
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'study_log'
                    """)
                    columns = [row[0] for row in cur.fetchall()]
                    app.logger.info(f"study_logテーブルのカラム: {columns}")
                    
                    # sourceカラムが存在するかチェック
                    if 'source' in columns:
                        # Delete all study history for the user and source
                        cur.execute("""
                            DELETE FROM study_log 
                            WHERE user_id = %s AND source = %s
                        """, (current_user.id, source))
                        deleted_study_logs = cur.rowcount
                        app.logger.info(f"削除されたstudy_logレコード数: {deleted_study_logs}")
                    else:
                        app.logger.warning("study_logテーブルにsourceカラムが存在しません")
                        # sourceカラムがない場合は、card_idを通じてcardsテーブルからsourceを取得して削除
                        try:
                            cur.execute("""
                                DELETE FROM study_log 
                                WHERE user_id = %s AND card_id IN (
                                    SELECT id FROM cards WHERE source = %s
                                )
                            """, (current_user.id, source))
                            deleted_study_logs = cur.rowcount
                            app.logger.info(f"cardsテーブル経由で削除されたstudy_logレコード数: {deleted_study_logs}")
                        except Exception as e:
                            app.logger.error(f"cardsテーブル経由での削除エラー: {e}")
                            deleted_study_logs = 0
                        
                except Exception as e:
                    app.logger.error(f"study_logテーブル構造確認エラー: {e}")
                    deleted_study_logs = 0
                
                # Delete all chunk progress for the user and source
                cur.execute("""
                    DELETE FROM chunk_progress 
                    WHERE user_id = %s AND source = %s
                """, (current_user.id, source))
                deleted_chunk_progress = cur.rowcount
                app.logger.info(f"削除されたchunk_progressレコード数: {deleted_chunk_progress}")
                
                # Delete user settings for the source
                try:
                    cur.execute("""
                        DELETE FROM user_settings 
                        WHERE user_id = %s AND source = %s
                    """, (str(current_user.id), source))
                    deleted_user_settings = cur.rowcount
                    app.logger.info(f"削除されたuser_settingsレコード数: {deleted_user_settings}")
                except Exception as e:
                    app.logger.error(f"user_settings削除エラー: {e}")
                    deleted_user_settings = 0
                
                # Clear any cached data for this user and source
                clear_user_cache(current_user.id, source)
                
                flash(f'{source}の学習履歴をリセットしました。', 'success')
                app.logger.info(f"履歴リセット完了: study_log={deleted_study_logs}, chunk_progress={deleted_chunk_progress}, user_settings={deleted_user_settings}")
                conn.commit()  # ここでコミット
                
    except Exception as e:
        flash('履歴のリセット中にエラーが発生しました。', 'error')
        app.logger.error(f"履歴リセットエラー: {str(e)}")
        import traceback
        app.logger.error(f"詳細エラー: {traceback.format_exc()}")
    
    return redirect(url_for('admin'))

@app.route('/prepare/<source>')
@login_required
def prepare(source):
    """学習進捗確認画面（設定変更機能は削除）"""
    user_id = str(current_user.id)
    
    try:
        # 教材の詳細情報を取得（追加）
        full_material_name = source  # デフォルト値
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        SELECT DISTINCT subject, grade 
                        FROM image 
                        WHERE source = %s 
                        LIMIT 1
                    ''', (source,))
                    material_info = cur.fetchone()
            
            if material_info:
                subject, grade = material_info
                full_material_name = f"{source}（{subject}{grade}）"
        except Exception as e:
            app.logger.error(f"教材情報取得エラー: {e}")
        
        # 保存済み設定を取得
        saved_page_range = ''
        saved_difficulty = ''
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        SELECT page_range, difficulty FROM user_settings
                        WHERE user_id = %s AND source = %s
                    ''', (user_id, source))
                    result = cur.fetchone()
            
            if result:
                saved_page_range = result[0] or ''
                saved_difficulty = result[1] or ''
                # セッションにも保存（学習時に使用）
                session['page_range'] = saved_page_range
                session['difficulty'] = saved_difficulty
        except Exception as e:
            app.logger.error(f"設定取得エラー: {e}")

        # 設定が未完了の場合はダッシュボードにリダイレクト
        # if not saved_page_range:
        #     flash("学習設定が必要です。ページ範囲と難易度を設定してください。")
        #     return redirect(url_for('dashboard'))

        # 詳細進捗情報を取得
        stages_info = get_detailed_progress_for_all_stages(user_id, source, saved_page_range, saved_difficulty)
        
        if not stages_info:
            stages_info = create_fallback_stage_info(source, saved_page_range, saved_difficulty, user_id)

        is_mastered = is_all_stages_perfect(user_id, source, saved_page_range, saved_difficulty)
        return render_template(
            'prepare.html',
            source=source,
            full_material_name=full_material_name,
            stages_info=stages_info,
            saved_page_range=saved_page_range,
            saved_difficulty=saved_difficulty,
            is_mastered=is_mastered
        )
        
    except Exception as e:
        app.logger.error(f"準備画面エラー: {e}")
        flash("準備画面でエラーが発生しました")
        return redirect(url_for('admin'))

def is_all_stages_perfect(user_id, source, page_range, difficulty):
    return (
        is_stage_perfect(user_id, source, 1, page_range, difficulty) and
        is_stage_perfect(user_id, source, 2, page_range, difficulty) and
        is_stage_perfect(user_id, source, 3, page_range, difficulty)
    )

@app.route('/start_chunk/<source>/<int:stage>/<int:chunk_number>/<mode>')
@login_required
def start_chunk(source, stage, chunk_number, mode):
    """指定チャンクの学習を開始（最適化版）"""
    try:
        user_id = str(current_user.id)
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        # セッションに学習情報を設定
        session['stage'] = stage
        session['current_source'] = source
        session['page_range'] = page_range
        session['difficulty'] = difficulty
        
        if mode == 'test':
            session['mode'] = 'test'
            session.pop('practicing_chunk', None)
            if stage == 1:
                session['current_chunk'] = chunk_number
        elif mode == 'practice':
            # ステージ2・3でも練習モードに対応
            if stage == 1:
                session['mode'] = 'chunk_practice'
                session['practicing_chunk'] = chunk_number
            else:
                session['mode'] = 'practice'
                session['practicing_chunk'] = chunk_number  # ステージ2・3でも chunk_number を保存
        
        # キャッシュクリア（学習開始時）
        clear_user_cache(user_id, source)
        
        flash(f"ステージ{stage} チャンク{chunk_number}の{mode}を開始します！")
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"学習開始エラー: {e}")
        flash("学習開始に失敗しました")
        return redirect(url_for('prepare', source=source))

@app.route('/start_chunk_practice/<source>/<int:chunk_number>')
@login_required
def start_chunk_practice(source, chunk_number):
    """チャンク練習を開始（必須）"""
    try:
        user_id = str(current_user.id)
        stage = session.get('stage', 1)
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        app.logger.info(f"[START_PRACTICE] チャンク{chunk_number}の練習開始: user_id={user_id}, stage={stage}")
        
        # 練習カードを取得
        if stage == 1:
            practice_cards = get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty)
        else:
            practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, chunk_number, page_range, difficulty)
        
        if practice_cards:
            # 練習モードに切り替え
            session['mode'] = 'chunk_practice'
            session['practicing_chunk'] = chunk_number
            session['current_source'] = source
            
            # キャッシュクリア
            clear_user_cache(user_id, source)
            
            app.logger.info(f"[START_PRACTICE] 練習カード{len(practice_cards)}問を開始")
            flash(f"🎯 チャンク{chunk_number}の練習を開始します！（{len(practice_cards)}問）")
        else:
            # 練習対象がない場合は設定画面に戻る
            app.logger.info(f"[START_PRACTICE] チャンク{chunk_number}は練習対象なし")
            flash(f"🌟 チャンク{chunk_number}は全問正解でした！")
            return redirect(url_for('prepare', source=source))
        
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"[START_PRACTICE] 練習開始エラー: {e}")
        flash("練習の開始に失敗しました")
        return redirect(url_for('prepare', source=source))

# ========== Redis除去版 パート12: 学習実行ルート ==========

@app.route('/study/<source>')
@login_required  
def study(source):
    """学習実行画面"""
    try:
        # セッションから必要な情報を取得
        stage = session.get('stage')
        mode = session.get('mode')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        current_chunk = session.get('current_chunk')

        if not all([stage, mode, current_chunk]):
            app.logger.error("必要なセッション情報が不足しています")
            flash("学習情報が正しく設定されていません。準備画面からやり直してください。")
            return redirect(url_for('prepare', source=source))

        # チャンク進捗の取得
        chunk_progress = get_or_create_chunk_progress_universal(
            current_user.id, source, stage, page_range, difficulty
        )

        if not chunk_progress:
            app.logger.error("チャンク進捗の取得に失敗しました")
            flash("学習情報の取得に失敗しました。準備画面からやり直してください。")
            return redirect(url_for('prepare', source=source))

        # テストモードの場合
        if mode == 'test':
            # カードの取得
            cards = get_study_cards_fast(
                source, stage, mode, page_range,
                str(current_user.id), difficulty, current_chunk
            )

            if not cards:
                app.logger.error("テストカードの取得に失敗しました")
                flash("問題の取得に失敗しました。準備画面からやり直してください。")
                return redirect(url_for('prepare', source=source))

            app.logger.info(f"テスト開始: {len(cards)}問")
            return render_template(
                'study.html',
                cards=cards,
                source=source,
                stage=stage,
                mode=mode,
                current_chunk=current_chunk,
                chunk_progress=chunk_progress
            )

        # 練習モードの場合
        elif mode in ['practice', 'chunk_practice']:
            cards = get_chunk_practice_cards_universal(
                current_user.id, source, stage, current_chunk,
                page_range, difficulty
            )

            if not cards:
                app.logger.error("練習カードの取得に失敗しました")
                flash("問題の取得に失敗しました。準備画面からやり直してください。")
                return redirect(url_for('prepare', source=source))

            app.logger.info(f"練習開始: {len(cards)}問")
            return render_template(
                'study.html',
                cards=cards,
                source=source,
                stage=stage,
                mode=mode,
                current_chunk=current_chunk,
                chunk_progress=chunk_progress
            )

        else:
            app.logger.error(f"不正なモード: {mode}")
            flash("不正な学習モードです。準備画面からやり直してください。")
            return redirect(url_for('prepare', source=source))

    except Exception as e:
        app.logger.error(f"学習画面表示エラー: {e}")
        flash("エラーが発生しました。準備画面からやり直してください。")
        return redirect(url_for('prepare', source=source))

# ========== Redis除去版 パート13: ログ記録とデバッグルート（最終パート） ==========


@app.route('/log_result', methods=['POST'])
def log_result():
    try:
        import sys
        import traceback
        data = request.get_json()
        print('log_result data:', data, file=sys.stderr)
        print('session:', dict(session), file=sys.stderr)
        print('current_user.is_authenticated:', getattr(current_user, 'is_authenticated', None), file=sys.stderr)

        if not data:
            print('No data provided', file=sys.stderr)
            return jsonify({'error': 'No data provided'}), 400

        # 必要なデータの存在確認
        required_fields = ['word_id', 'is_correct', 'chunk_id']
        if not all(field in data for field in required_fields):
            print('Missing required fields', file=sys.stderr)
            return jsonify({'error': 'Missing required fields'}), 400

        word_id = data['word_id']
        is_correct = data['is_correct']
        chunk_id = data['chunk_id']

        # セッション・ユーザーの必須情報チェック
        if not getattr(current_user, 'is_authenticated', False):
            print('User not authenticated', file=sys.stderr)
            return 'User not authenticated', 401
        if not session.get('current_source') or not session.get('stage'):
            print('Session missing current_source or stage', file=sys.stderr)
            return 'Session missing current_source or stage', 400

        # セッションから学習データを取得・なければ初期化
        study_data = session.get('study_data')
        if not study_data:
            study_data = {'word_history': {}}
            session['study_data'] = study_data

        # 単語の学習履歴を更新
        word_history = study_data.get('word_history', {})
        if word_id not in word_history:
            word_history[word_id] = {
                'correct_count': 0,
                'incorrect_count': 0,
                'last_result': None
            }
        
        if is_correct:
            word_history[word_id]['correct_count'] += 1
        else:
            word_history[word_id]['incorrect_count'] += 1
        word_history[word_id]['last_result'] = is_correct

        # セッションを更新
        study_data['word_history'] = word_history
        session['study_data'] = study_data

        # データベースに結果を記録（study_logテーブルに統一、sourceカラム名修正）
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    '''
                    INSERT INTO study_log (user_id, source, stage, card_id, result, mode)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ''',
                    (
                        str(current_user.id),
                        session.get('current_source'),
                        session.get('stage', 1),
                        word_id,
                        'known' if is_correct else 'unknown',
                        session.get('mode', 'test')
                    )
                )
                conn.commit()
        
        return jsonify({'success': True})

    except Exception as e:
        import sys
        import traceback
        print(f"Error in log_result: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        # 500エラー時はJSONで返す
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

# ========== 英単語専用システム ==========

@app.route('/vocabulary')
@login_required
def vocabulary_home():
    """英単語学習のホーム画面"""
    try:
        # ユーザーの学習履歴を取得（vocabulary_study_logテーブルから）
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT DISTINCT source, COUNT(*) as total_words,
                           COUNT(CASE WHEN result = 'known' THEN 1 END) as known_words
                    FROM vocabulary_study_log 
                    WHERE user_id = %s
                    GROUP BY source
                ''', (str(current_user.id),))
                vocabulary_sources = cur.fetchall()
        
        # 各セットの総単語数も取得
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT source, COUNT(*) as total_available
                    FROM vocabulary_words 
                    GROUP BY source
                ''')
                total_available = {row['source']: row['total_available'] for row in cur.fetchall()}
        
        # 結果をマージ
        for source in vocabulary_sources:
            source['total_available'] = total_available.get(source['source'], 0)
        
        return render_template('vocabulary/home.html', vocabulary_sources=vocabulary_sources)
    except Exception as e:
        app.logger.error(f"英単語ホーム画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('admin'))

@app.route('/vocabulary/chapters/<source>')
@login_required
def vocabulary_chapters(source):
    """英単語章選択画面"""
    try:
        # ソースタイトルの設定
        source_titles = {
            'basic': '基本英単語帳',
            'toeic': 'TOEIC単語帳',
            'university': '大学受験単語帳'
        }
        source_title = source_titles.get(source, source)
        
        # 章データを取得（仮の実装 - 後でデータベースから取得）
        chapters = [
            {
                'id': 1,
                'title': 'Chapter 1: 基本単語',
                'description': '日常生活でよく使われる基本単語',
                'total_words': 100,
                'chunk_count': 5
            },
            {
                'id': 2,
                'title': 'Chapter 2: 動詞',
                'description': '重要な動詞の学習',
                'total_words': 80,
                'chunk_count': 4
            },
            {
                'id': 3,
                'title': 'Chapter 3: 形容詞',
                'description': '形容詞の学習',
                'total_words': 60,
                'chunk_count': 3
            }
        ]
        
        return render_template('vocabulary/chapters.html',
                             source=source,
                             source_title=source_title,
                             chapters=chapters)
        
    except Exception as e:
        app.logger.error(f"英単語章選択エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('vocabulary_home'))

@app.route('/vocabulary/chunks/<source>/<int:chapter_id>')
@login_required
def vocabulary_chunks(source, chapter_id):
    """英単語チャンク選択画面"""
    try:
        # ソースタイトルの設定
        source_titles = {
            'basic': '基本英単語帳',
            'toeic': 'TOEIC単語帳',
            'university': '大学受験単語帳'
        }
        source_title = source_titles.get(source, source)
        
        # 章タイトルの設定（仮の実装）
        chapter_titles = {
            1: 'Chapter 1: 基本単語',
            2: 'Chapter 2: 動詞',
            3: 'Chapter 3: 形容詞'
        }
        chapter_title = chapter_titles.get(chapter_id, f'Chapter {chapter_id}')
        
        # チャンクデータを取得（仮の実装 - 後でデータベースから取得）
        chunks = []
        chunk_count = 5 if chapter_id == 1 else 4 if chapter_id == 2 else 3
        
        # 各チャンクの進捗状況をチェック
        for i in range(1, chunk_count + 1):
            try:
                progress = get_vocabulary_chunk_progress(str(current_user.id), source, chapter_id, i)
                is_completed = progress.get('is_completed', False) if progress else False
                is_passed = progress.get('is_passed', False) if progress else False
                correct_count = progress.get('correct_count', 0) if progress else 0
                
                app.logger.info(f"チャンク{i}進捗: completed={is_completed}, passed={is_passed}, correct_count={correct_count}, progress={progress}")
                
                chunks.append({
                    'chunk_number': i,
                    'title': f'チャンク {i}',
                    'description': f'{20}単語の学習',
                    'total_words': 20,
                    'correct_count': correct_count,
                    'is_completed': is_completed,
                    'is_passed': is_passed
                })
            except Exception as e:
                app.logger.error(f"チャンク{i}の進捗取得エラー: {e}")
                chunks.append({
                    'chunk_number': i,
                    'title': f'チャンク {i}',
                    'description': f'{20}単語の学習',
                    'total_words': 20,
                    'correct_count': 0,
                    'is_completed': False,
                    'is_passed': False
                })
        
        return render_template('vocabulary/chunks.html',
                             source=source,
                             source_title=source_title,
                             chapter_id=chapter_id,
                             chapter_title=chapter_title,
                             chunks=chunks)
        
    except Exception as e:
        app.logger.error(f"英単語チャンク選択エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('vocabulary_home'))

@app.route('/vocabulary/start/<source>/<int:chapter_id>/<int:chunk_number>')
@app.route('/vocabulary/start/<source>/<int:chapter_id>/<int:chunk_number>/<mode>')
@login_required
def vocabulary_start(source, chapter_id, chunk_number, mode=None):
    """英単語学習開始"""
    try:
        app.logger.info(f"英単語学習開始: user={current_user.id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, mode={mode}")
        
        # 指定されたチャンクの単語を取得
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('''
                        SELECT id, word, meaning, example_sentence
                        FROM vocabulary_words 
                        WHERE source = %s 
                        ORDER BY RANDOM() 
                        LIMIT 20
                    ''', (source,))
                    words = cur.fetchall()
            
            if not words:
                app.logger.warning(f"単語が見つかりません: source={source}")
                flash("単語が見つかりませんでした")
                return redirect(url_for('vocabulary_home'))
                
        except Exception as e:
            app.logger.error(f"データベース接続エラー: {e}")
            flash("データベース接続エラーが発生しました")
            return redirect(url_for('vocabulary_home'))
        
        # 4択問題の選択肢を生成
        words_with_choices = []
        for word in words:
            # 正解の選択肢
            correct_choice = word['meaning']
            
            # 他の単語から3つの選択肢をランダムに選択
            other_meanings = [w['meaning'] for w in words if w['id'] != word['id']]
            import random
            wrong_choices = random.sample(other_meanings, min(3, len(other_meanings)))
            
            # 4つの選択肢を作成（正解を含む）
            all_choices = [correct_choice] + wrong_choices
            random.shuffle(all_choices)
            
            # 正解のインデックスを記録
            correct_index = all_choices.index(correct_choice)
            
            words_with_choices.append({
                'id': word['id'],
                'word': word['word'],
                'meaning': word['meaning'],
                'example': word['example_sentence'],
                'choices': all_choices,
                'correct_index': correct_index
            })
        
        # セッションに学習情報を保存
        session_id = str(datetime.now().timestamp())
        vocabulary_session = {
            'source': source,
            'chapter_id': chapter_id,
            'chunk_number': chunk_number,
            'mode': mode,  # 'review' または 'retest' または None
            'words': words_with_choices,
            'current_index': 0,
            'results': [],
            'start_time': datetime.now().isoformat(),
            'session_id': session_id
        }
        
        # セッションに保存
        try:
            session['vocabulary_session'] = vocabulary_session
            session.modified = True  # セッションの変更を確実に保存
            
            app.logger.info(f"セッション保存完了: session_id={session_id}, words_count={len(words)}")
            
            # リダイレクト先のURLを生成
            study_url = url_for('vocabulary_study', source=source)
            app.logger.info(f"学習画面にリダイレクト: {study_url}")
            
            return redirect(study_url)
            
        except Exception as e:
            app.logger.error(f"セッション保存エラー: {e}")
            flash("セッション保存エラーが発生しました")
            return redirect(url_for('vocabulary_home'))
        
    except Exception as e:
        app.logger.error(f"英単語学習開始エラー: {e}")
        flash("学習の開始に失敗しました")
        return redirect(url_for('vocabulary_home'))

@app.route('/vocabulary/study/<source>')
@login_required
def vocabulary_study(source):
    """英単語学習画面"""
    try:
        app.logger.info(f"英単語学習画面アクセス: user={current_user.id}, source={source}")
        
        vocabulary_session = session.get('vocabulary_session')
        app.logger.info(f"セッション情報: {vocabulary_session}")
        
        if not vocabulary_session:
            app.logger.warning(f"セッション情報が見つかりません: user={current_user.id}, source={source}")
            flash("学習セッションが見つかりません。学習を再開始してください。")
            return redirect(url_for('vocabulary_home'))
        
        # セッションの整合性チェック
        if 'current_index' not in vocabulary_session or 'words' not in vocabulary_session:
            app.logger.warning(f"セッション情報が不完全: {vocabulary_session}")
            flash("学習セッションが破損しています。学習を再開始してください。")
            return redirect(url_for('vocabulary_home'))
        
        # セッションの整合性チェック
        if 'current_index' not in vocabulary_session or 'words' not in vocabulary_session:
            app.logger.warning(f"セッション情報が不完全: {vocabulary_session}")
            flash("学習セッションが破損しています")
            return redirect(url_for('vocabulary_home'))
        
        if vocabulary_session['source'] != source:
            app.logger.warning(f"ソースが一致しません: session_source={vocabulary_session['source']}, request_source={source}")
            flash("学習セッションが見つかりません")
            return redirect(url_for('vocabulary_home'))
        
        current_index = vocabulary_session['current_index']
        words = vocabulary_session['words']
        
        # 高速チェック（ログ出力を最小限に）
        if current_index >= len(words):
            # 学習完了
            return redirect(url_for('vocabulary_result', source=source))
        
        current_word = words[current_index]
        
        return render_template('vocabulary/study.html', 
                             word=current_word, 
                             current_index=current_index + 1,
                             total_words=len(words),
                             source=source,
                             vocabulary_session=vocabulary_session)
        
    except Exception as e:
        app.logger.error(f"英単語学習画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('vocabulary_home'))

@app.route('/vocabulary/answer', methods=['POST'])
@login_required
def vocabulary_answer():
    """英単語の回答処理"""
    try:
        data = request.get_json()
        selected_index = data.get('selected_index')  # 選択された選択肢のインデックス（0-3）
        
        vocabulary_session = session.get('vocabulary_session')
        if not vocabulary_session:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        current_index = vocabulary_session['current_index']
        words = vocabulary_session['words']
        
        if current_index >= len(words):
            return jsonify({'error': '学習が完了しています'}), 400
        
        # 結果を記録
        current_word = words[current_index]
        is_correct = selected_index == current_word['correct_index']
        result = 'correct' if is_correct else 'incorrect'
        
        vocabulary_session['results'].append({
            'word_id': current_word['id'],
            'word': current_word['word'],
            'meaning': current_word['meaning'],
            'selected_choice': current_word['choices'][selected_index],
            'correct_choice': current_word['choices'][current_word['correct_index']],
            'selected_index': selected_index,
            'correct_index': current_word['correct_index'],
            'result': result
        })
        
        # 次の単語へ（即座に更新）
        vocabulary_session['current_index'] += 1
        session['vocabulary_session'] = vocabulary_session
        session.modified = True  # セッションの変更を確実に保存
        
        # 学習完了かチェック
        if vocabulary_session['current_index'] >= len(words):
            # 完了時はデータベース記録を確実に実行
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO vocabulary_study_log 
                            (user_id, word_id, result, source, study_date, session_id, chapter_id, chunk_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            str(current_user.id),
                            current_word['id'],
                            result,
                            vocabulary_session['source'],
                            datetime.now(),
                            vocabulary_session.get('session_id', str(datetime.now().timestamp())),
                            vocabulary_session.get('chapter_id'),
                            vocabulary_session.get('chunk_number')
                        ))
                        conn.commit()
            except Exception as e:
                app.logger.error(f"データベース記録エラー: {e}")
            
            return jsonify({'status': 'completed'})
        else:
            # 継続時はバックグラウンドでデータベース記録
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO vocabulary_study_log 
                            (user_id, word_id, result, source, study_date, session_id, chapter_id, chunk_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            str(current_user.id),
                            current_word['id'],
                            result,
                            vocabulary_session['source'],
                            datetime.now(),
                            vocabulary_session.get('session_id', str(datetime.now().timestamp())),
                            vocabulary_session.get('chapter_id'),
                            vocabulary_session.get('chunk_number')
                        ))
                        conn.commit()
            except Exception as e:
                app.logger.error(f"データベース記録エラー: {e}")
            
            return jsonify({'status': 'continue'})
            
    except Exception as e:
        app.logger.error(f"英単語回答処理エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vocabulary/complete', methods=['POST'])
@login_required
def vocabulary_complete():
    """英単語学習完了処理"""
    try:
        data = request.get_json()
        results = data.get('results', [])
        
        vocabulary_session = session.get('vocabulary_session')
        if not vocabulary_session:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        # セッションに結果を保存
        vocabulary_session['results'] = results
        session['vocabulary_session'] = vocabulary_session
        session.modified = True
        
        app.logger.info(f"英単語学習完了: user={current_user.id}, results_count={len(results)}")
        
        # データベースにすべての結果を記録
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for result in results:
                        cur.execute('''
                            INSERT INTO vocabulary_study_log 
                            (user_id, word_id, result, source, study_date, session_id, chapter_id, chunk_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            str(current_user.id),
                            result['word_id'],
                            result['result'],
                            vocabulary_session['source'],
                            datetime.now(),
                            vocabulary_session.get('session_id', str(datetime.now().timestamp())),
                            vocabulary_session.get('chapter_id'),
                            vocabulary_session.get('chunk_number')
                        ))
                    conn.commit()
                    app.logger.info(f"データベース記録完了: {len(results)}件")
        except Exception as e:
            app.logger.error(f"データベース記録エラー: {e}")
            # データベースエラーでもセッションは保存されているので続行
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        app.logger.error(f"英単語完了処理エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vocabulary/result/<source>')
@login_required
def vocabulary_result(source):
    """英単語学習結果画面"""
    try:
        app.logger.info(f"結果ページアクセス: user={current_user.id}, source={source}")
        
        vocabulary_session = session.get('vocabulary_session')
        app.logger.info(f"セッション情報: {vocabulary_session}")
        
        if not vocabulary_session or vocabulary_session['source'] != source:
            app.logger.warning(f"セッションが見つからないか、ソースが一致しません: session={vocabulary_session}, source={source}")
            flash("学習セッションが見つかりません")
            return redirect(url_for('vocabulary_home'))
        
        results = vocabulary_session.get('results', [])
        
        # 結果が空の場合は、データベースから取得を試行
        if not results:
            try:
                with get_db_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute('''
                            SELECT vw.word, vw.meaning, vsl.result
                            FROM vocabulary_study_log vsl
                            JOIN vocabulary_words vw ON vsl.word_id = vw.id
                            WHERE vsl.user_id = %s AND vsl.source = %s AND vsl.session_id = %s
                            ORDER BY vsl.study_date
                        ''', (str(current_user.id), source, vocabulary_session.get('session_id')))
                        db_results = cur.fetchall()
                        
                        # データベースの結果をセッション形式に変換
                        results = [{
                            'word': r['word'],
                            'meaning': r['meaning'],
                            'result': r['result']
                        } for r in db_results]
                        
                        # セッションに保存
                        vocabulary_session['results'] = results
                        session['vocabulary_session'] = vocabulary_session
                        session.modified = True
                        
            except Exception as e:
                app.logger.error(f"データベースからの結果取得エラー: {e}")
        
        # 結果がまだ空の場合は、エラーページを表示
        if not results:
            app.logger.warning(f"セッションとデータベースの両方から結果を取得できませんでした: user={current_user.id}, source={source}")
            # フラッシュメッセージを表示してホームにリダイレクト
            flash("学習結果の取得に失敗しました。再度学習を開始してください。")
            return redirect(url_for('vocabulary_home'))
        
        app.logger.info(f"結果データ取得成功: {len(results)}件")
        
        app.logger.info(f"結果ページ表示: user={current_user.id}, source={source}, results_count={len(results)}")
        
        unknown_words = [r for r in results if r['result'] == 'incorrect']
        known_count = len([r for r in results if r['result'] == 'correct'])
        unknown_count = len(unknown_words)
        all_words = results  # 全問題の結果
        
        # チャンク情報を取得
        chapter_id = vocabulary_session.get('chapter_id')
        chunk_number = vocabulary_session.get('chunk_number')
        mode = vocabulary_session.get('mode')
        
        # チャンク進捗を更新
        if chapter_id and chunk_number:
            app.logger.info(f"チャンク進捗更新: user={current_user.id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, unknown_count={unknown_count}, mode={mode}")
            
            # 学習完了として記録
            update_success = update_vocabulary_chunk_progress(
                str(current_user.id), source, chapter_id, chunk_number,
                is_completed=True
            )
            app.logger.info(f"学習完了更新結果: {update_success}")
            
            # 全問正解の場合、合格ステータスも更新
            if known_count == len(results) and mode != 'retest':
                app.logger.info(f"全問正解判定: 合格ステータスを更新")
                update_success = update_vocabulary_chunk_progress(
                    str(current_user.id), source, chapter_id, chunk_number,
                    is_passed=True
                )
                app.logger.info(f"合格ステータス更新結果: {update_success}")
                # キャッシュをクリア
                clear_user_cache(str(current_user.id), source)
        
        # ソースタイトルの設定
        source_titles = {
            'basic': '基本英単語帳',
            'toeic': 'TOEIC単語帳',
            'university': '大学受験単語帳'
        }
        source_title = source_titles.get(source, source)
        
        # 章タイトルの設定（仮の実装）
        chapter_titles = {
            1: 'Chapter 1: 基本単語',
            2: 'Chapter 2: 動詞',
            3: 'Chapter 3: 形容詞'
        }
        chapter_title = chapter_titles.get(chapter_id, f'Chapter {chapter_id}') if chapter_id else None
        
        # セッションをクリア（テンプレート表示前に実行）
        session.pop('vocabulary_session', None)
        
        return render_template('vocabulary/result.html',
                             unknown_words=unknown_words,
                             all_words=all_words,
                             known_count=known_count,
                             unknown_count=unknown_count,
                             total_count=len(results),
                             source=source,
                             source_title=source_title,
                             chapter_id=chapter_id,
                             chapter_title=chapter_title,
                             chunk_number=chunk_number)
        
    except Exception as e:
        app.logger.error(f"英単語結果画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('vocabulary_home'))

# ========== 英単語管理機能 ==========

@app.route('/vocabulary/admin')
@login_required
def vocabulary_admin():
    """英単語管理画面（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('vocabulary_home'))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('''
                    SELECT source, COUNT(*) as word_count
                    FROM vocabulary_words 
                    GROUP BY source
                    ORDER BY source
                ''')
                sources = cur.fetchall()
        
        return render_template('vocabulary/admin.html', sources=sources)
        
    except Exception as e:
        app.logger.error(f"英単語管理画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('vocabulary_home'))

@app.route('/vocabulary/upload', methods=['POST'])
@login_required
def vocabulary_upload():
    """英単語データのアップロード（管理者のみ）"""
    if not current_user.is_admin:
        return jsonify({'error': '管理者権限が必要です'}), 403
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        source = request.form.get('source', 'default')
        
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
        
        reader = csv.DictReader(csv_data)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for row in reader:
                    cur.execute('''
                        INSERT INTO vocabulary_words (word, meaning, example_sentence, source)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (word, source) DO UPDATE SET
                        meaning = EXCLUDED.meaning,
                        example_sentence = EXCLUDED.example_sentence
                    ''', (
                        row.get('word', '').strip(),
                        row.get('meaning', '').strip(),
                        row.get('example', '').strip(),
                        source
                    ))
                conn.commit()
        
        return jsonify({'success': True, 'message': f'{len(csv_data)-1}個の単語を登録しました'})
        
    except Exception as e:
        app.logger.error(f"英単語アップロードエラー: {e}")
        return jsonify({'error': str(e)}), 500



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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 指定された科目の問題を取得
                cur.execute('''
                    SELECT id, question, correct_answer, acceptable_answers, answer_suffix, explanation, image_url
                    FROM social_studies_questions 
                    WHERE subject = %s 
                    ORDER BY RANDOM() 
                    LIMIT 10
                ''', (subject,))
                questions = cur.fetchall()
                
                if not questions:
                    flash('この科目の問題が見つかりません', 'error')
                    return redirect(url_for('admin'))
                
                return render_template('social_studies/quiz.html', 
                                     questions=questions, 
                                     subject=subject)
    except Exception as e:
        app.logger.error(f"社会科クイズ画面エラー: {e}")
        flash('問題の取得に失敗しました', 'error')
        return redirect(url_for('admin'))

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
                total_textbooks = cur.fetchone()['total_textbooks']
                
                cur.execute('SELECT COUNT(*) as total_units FROM social_studies_units')
                total_units = cur.fetchone()['total_units']
                
                cur.execute('SELECT COUNT(*) as total_questions FROM social_studies_questions')
                total_questions = cur.fetchone()['total_questions']
                
                cur.execute('SELECT COUNT(*) as total_study_logs FROM social_studies_study_log')
                total_study_logs = cur.fetchone()['total_study_logs']
                
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
        return redirect(url_for('admin'))

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
                           q.image_name, q.image_url, t.name as textbook_name, u.name as unit_name,
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
                
                if question['textbook_id']:
                    cur.execute('SELECT * FROM social_studies_textbooks WHERE id = %s', (question['textbook_id'],))
                    textbook_info = cur.fetchone()
                
                if question['unit_id']:
                    cur.execute('SELECT * FROM social_studies_units WHERE id = %s', (question['unit_id'],))
                    unit_info = cur.fetchone()
                
                return render_template('social_studies/edit_question.html', 
                                     question=question, 
                                     textbook_info=textbook_info, 
                                     unit_info=unit_info)
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
                               q.image_name, q.image_url, t.name as textbook_name, u.name as unit_name
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
                            explanation = %s, difficulty_level = %s, image_name = %s, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (subject, textbook_id, unit_id, question_text, correct_answer, 
                          acceptable_answers, answer_suffix, explanation, difficulty_level, 
                          image_name, question_id))
                    
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









# ========== 単元管理 ==========

# 単元管理ルートは削除 - 統一管理画面で代替

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

# ========== メイン管理画面 ==========

@app.route('/admin')
@login_required
def admin():
    """メイン管理画面（管理者のみ）"""
    if not current_user.is_admin:
        flash("管理者権限が必要です")
        return redirect(url_for('login')) 
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) as total_users FROM users')
                total_users = cur.fetchone()['total_users']
                
                cur.execute('SELECT COUNT(*) as total_questions FROM social_studies_questions')
                total_questions = cur.fetchone()['total_questions']
                
                cur.execute('SELECT COUNT(*) as total_study_logs FROM social_studies_study_log')
                total_study_logs = cur.fetchone()['total_study_logs']
                
                return render_template('admin.html',
                                     total_users=total_users,
                                     total_questions=total_questions,
                                     total_study_logs=total_study_logs)
    except Exception as e:
        app.logger.error(f"管理画面エラー: {e}")
        flash('管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('login'))

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
        
        # ヘッダー行（1行目）
        csv_data.append(['単元名', '章番号', '説明'])
        
        # 入力例行（2行目、コメントアウト）
        csv_data.append(['# 新しい単元名', '# 1', '# 新しい単元の説明'])
        
        # テンプレート行を追加（新しい単元追加用）
        csv_data.append(['新しい単元名', '1', '新しい単元の説明'])
        csv_data.append(['', '2', ''])
        csv_data.append(['', '3', ''])
        
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
            '単元名', '章番号', '問題文', '正解', '許容回答', '解答欄の補足', 
            '解説', '難易度', '画像URL', '画像タイトル', '登録日'
        ])
        
        # 入力例行（2行目、コメントアウト）
        csv_data.append([
            '# 単元名', '# 1', '# 新しい問題文', '# 新しい正解', '# 許容回答1,許容回答2', 
            '# 解答欄の補足', '# 解説', '# 基本', '# https://s3.ap-northeast-1.wasabisys.com/so-image/social studies/geography/', '# 1-1.jpg', '# '
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
        
        # テンプレート行を追加（新しい問題追加用）
        csv_data.append([
            '単元名', '1', '新しい問題文', '新しい正解', '許容回答1,許容回答2', 
            '解答欄の補足', '解説', '基本', f"{base_image_url}/", '1-1.jpg', ''
        ])
        csv_data.append(['', '2', '', '', '', '', '', '基本', f"{base_image_url}/", '2-1.jpg', ''])
        csv_data.append(['', '3', '', '', '', '', '', '基本', f"{base_image_url}/", '3-1.jpg', ''])
        
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
            '教材名', '単元名', '問題文', '正解', '許容回答', '解答欄の補足', '解説', '難易度', '画像URL', '画像タイトル'
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
                base_image_url = f"https://s3.ap-northeast-1.wasabisys.com/{os.getenv('WASABI_BUCKET')}/{result['wasabi_folder_path'] or 'question_images'}/{chapter_number}"
                
                # 固定情報行（2行目、コメントアウト）
                csv_data.append([
                    f'# {textbook_name}', f'# {unit_name}', '# 新しい問題文', '# 新しい正解', '# 許容回答1,許容回答2', 
                    '# 解答欄の補足', '# 解説', '# 基本', f'# {base_image_url}/1.jpg', '# 1.jpg'
                ])
                
                # 既存の問題データを取得
                cur.execute('''
                    SELECT question, correct_answer, acceptable_answers, answer_suffix, 
                           explanation, difficulty_level, image_url, image_title
                    FROM social_studies_questions
                    WHERE textbook_id = %s AND unit_id = %s
                    ORDER BY id
                ''', (textbook_id, unit_id))
                existing_questions = cur.fetchall()
        
        # 既存の問題データを追加
        for question in existing_questions:
            csv_data.append([
                textbook_name,
                unit_name,
                question['question'] or '',
                question['correct_answer'] or '',
                question['acceptable_answers'] or '',
                question['answer_suffix'] or '',
                question['explanation'] or '',
                question['difficulty_level'] or '基本',
                question['image_url'] or base_image_url,
                question['image_title'] or ''
            ])
        
        # 新しい問題追加用のテンプレート行を追加
        csv_data.append([
            textbook_name, unit_name, '新しい問題文', '新しい正解', '許容回答1,許容回答2', 
            '解答欄の補足', '解説', '基本', f"{base_image_url}/1.jpg", '1.jpg'
        ])
        csv_data.append([textbook_name, unit_name, '', '', '', '', '', '基本', f"{base_image_url}/2.jpg", '2.jpg'])
        csv_data.append([textbook_name, unit_name, '', '', '', '', '', '基本', f"{base_image_url}/3.jpg", '3.jpg'])
        
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
                        
                        # 教材名と単元名の取得（オプション）
                        csv_textbook_name = row.get('教材名', '').strip()
                        csv_unit_name = row.get('単元名', '').strip()
                        
                        # オプションフィールドの取得（日本語ヘッダー対応）
                        acceptable_answers = row.get('許容回答', '').strip()
                        explanation = row.get('解説', '').strip()
                        answer_suffix = row.get('解答欄の補足', '').strip()
                        difficulty_level = row.get('難易度', '').strip()
                        image_url = row.get('画像URL', '').strip()
                        image_title = row.get('画像タイトル', '').strip()
                        
                        # 問題が既に存在するかチェック
                        cur.execute('''
                            SELECT id FROM social_studies_questions 
                            WHERE question = %s AND correct_answer = %s AND textbook_id = %s AND unit_id = %s
                        ''', (question, correct_answer, textbook_id, unit_id))
                        if cur.fetchone():
                            app.logger.warning(f"行{row_num}: 同じ問題が既に存在します - {question}")
                            skipped_count += 1
                            continue
                        
                        # 問題を登録
                        cur.execute('''
                            INSERT INTO social_studies_questions 
                            (textbook_id, unit_id, question, correct_answer, acceptable_answers, 
                             answer_suffix, explanation, difficulty_level, image_url, image_title)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (textbook_id, unit_id, question, correct_answer, acceptable_answers,
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
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 教材情報取得
                cur.execute('SELECT id, name FROM social_studies_textbooks WHERE id = %s', (textbook_id,))
                textbook_info = cur.fetchone()
                # 単元情報取得
                cur.execute('SELECT id, name, chapter_number FROM social_studies_units WHERE id = %s AND textbook_id = %s', (unit_id, textbook_id))
                unit_info = cur.fetchone()
                # 問題リスト取得
                cur.execute('''
                    SELECT * FROM social_studies_questions
                    WHERE textbook_id = %s AND unit_id = %s
                    ORDER BY id DESC
                ''', (textbook_id, unit_id))
                questions = cur.fetchall()
    except Exception as e:
        app.logger.error(f"単元ごとの問題一覧取得エラー: {e}")
        flash('単元ごとの問題一覧の取得に失敗しました', 'error')
    
    return render_template(
        'social_studies/admin_unit_questions.html',
        textbook_info=textbook_info,
        unit_info=unit_info,
        questions=questions
    )

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
        except Exception as e:
            print(f"❌ データベース接続テスト失敗: {e}")
            
    except Exception as e:
        print(f"❌ データベース接続プール初期化エラー: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)