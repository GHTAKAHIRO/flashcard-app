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

# ========== 設定エリア ==========
load_dotenv(dotenv_path='dbname.env')

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
csrf = CSRFProtect(app)
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
        init_connection_pool()
    
    conn = None
    try:
        if db_pool:  # 🔥 追加: プールが存在するかチェック
            conn = db_pool.getconn()
        
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
            conn.rollback()
        app.logger.error(f"DB接続エラー: {e}")
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
    
    if current_user.is_authenticated:
        # 管理者の場合は管理者画面にリダイレクト
        if current_user.is_admin:
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# favicon.icoのルートを追加
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT DISTINCT source, subject, grade FROM image ORDER BY source')
                rows = cur.fetchall()
                sources = [{"source": r[0], "subject": r[1], "grade": r[2]} for r in rows]
                
                user_id = str(current_user.id)
                cur.execute('SELECT source, page_range, difficulty FROM user_settings WHERE user_id = %s', (user_id,))
                settings = cur.fetchall()
                saved_ranges = {}
                saved_difficulties = {}
                # 学習履歴チェックを追加
                settings_locked = {}
                
                for setting in settings:
                    source_name = setting[0]
                    saved_ranges[source_name] = setting[1] or ''
                    saved_difficulties[source_name] = setting[2] or ''
                    # 各教材の設定変更可否をチェック
                    settings_locked[source_name] = has_study_history(user_id, source_name)
        
        return render_template('dashboard.html', 
                             sources=sources, 
                             saved_ranges=saved_ranges, 
                             saved_difficulties=saved_difficulties,
                             settings_locked=settings_locked)  # ロック状態を渡す
    except Exception as e:
        app.logger.error(f"ダッシュボードエラー: {e}")
        flash("教材一覧の取得に失敗しました")
        return redirect(url_for('login'))

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
    
    return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

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
        return redirect(url_for('dashboard'))

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
        
        # 指定されたチャンクの単語を取得（仮の実装）
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
        
        # セッションに学習情報を保存
        session_id = str(datetime.now().timestamp())
        vocabulary_session = {
            'source': source,
            'chapter_id': chapter_id,
            'chunk_number': chunk_number,
            'mode': mode,  # 'review' または 'retest' または None
            'words': [{'id': w['id'], 'word': w['word'], 'meaning': w['meaning'], 'example': w['example_sentence']} for w in words],
            'current_index': 0,
            'results': [],
            'start_time': datetime.now().isoformat(),
            'session_id': session_id
        }
        
        # セッションに保存
        session['vocabulary_session'] = vocabulary_session
        session.modified = True  # セッションの変更を確実に保存
        
        app.logger.info(f"セッション保存完了: session_id={session_id}, words_count={len(words)}")
        
        # リダイレクト先のURLを生成
        study_url = url_for('vocabulary_study', source=source)
        app.logger.info(f"学習画面にリダイレクト: {study_url}")
        
        return redirect(study_url)
        
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
            flash("学習セッションが見つかりません")
            return redirect(url_for('vocabulary_home'))
        
        if vocabulary_session['source'] != source:
            app.logger.warning(f"ソースが一致しません: session_source={vocabulary_session['source']}, request_source={source}")
            flash("学習セッションが見つかりません")
            return redirect(url_for('vocabulary_home'))
        
        current_index = vocabulary_session['current_index']
        words = vocabulary_session['words']
        
        app.logger.info(f"学習状況: current_index={current_index}, total_words={len(words)}")
        
        if current_index >= len(words):
            # 学習完了
            app.logger.info(f"学習完了: 結果画面にリダイレクト")
            return redirect(url_for('vocabulary_result', source=source))
        
        current_word = words[current_index]
        
        app.logger.info(f"現在の単語: {current_word['word']}")
        
        return render_template('vocabulary/study.html', 
                             word=current_word, 
                             current_index=current_index + 1,
                             total_words=len(words),
                             source=source)
        
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
        result = data.get('result')  # 'known' or 'unknown'
        
        vocabulary_session = session.get('vocabulary_session')
        if not vocabulary_session:
            return jsonify({'error': 'セッションが見つかりません'}), 400
        
        current_index = vocabulary_session['current_index']
        words = vocabulary_session['words']
        
        if current_index >= len(words):
            return jsonify({'error': '学習が完了しています'}), 400
        
        # 結果を記録
        current_word = words[current_index]
        vocabulary_session['results'].append({
            'word_id': current_word['id'],
            'word': current_word['word'],
            'meaning': current_word['meaning'],
            'result': result
        })
        
        # 次の単語へ
        vocabulary_session['current_index'] += 1
        session['vocabulary_session'] = vocabulary_session
        
        # データベースに記録
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
        
        # 学習完了かチェック
        if vocabulary_session['current_index'] >= len(words):
            return jsonify({'status': 'completed'})
        else:
            return jsonify({'status': 'continue'})
            
    except Exception as e:
        app.logger.error(f"英単語回答処理エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vocabulary/result/<source>')
@login_required
def vocabulary_result(source):
    """英単語学習結果画面"""
    try:
        vocabulary_session = session.get('vocabulary_session')
        if not vocabulary_session or vocabulary_session['source'] != source:
            flash("学習セッションが見つかりません")
            return redirect(url_for('vocabulary_home'))
        
        results = vocabulary_session['results']
        unknown_words = [r for r in results if r['result'] == 'unknown']
        known_count = len([r for r in results if r['result'] == 'known'])
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
            if unknown_count == 0 and mode != 'retest':
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
        
        # セッションをクリア
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
        
        # CSVファイルを読み込み
        csv_data = file.read().decode('utf-8').splitlines()
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



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)