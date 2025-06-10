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
    """データベース接続プールを初期化"""
    global db_pool
    if db_pool is None:
        try:
            db_pool = psycopg2.pool.ThreadedConnectionPool(
                2,   # 最小接続数
                10,  # 最大接続数
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=3,
                options='-c default_transaction_isolation=read\ committed'  # 修正: エスケープされたスペース
            )
            app.logger.info("🚀 データベース接続プール初期化完了")
        except Exception as e:
            app.logger.error(f"接続プール初期化エラー: {e}")
            # フォールバック処理
            try:
                db_pool = psycopg2.pool.ThreadedConnectionPool(
                    2, 10,
                    host=DB_HOST,
                    port=DB_PORT,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    connect_timeout=3
                )
                app.logger.info("🚀 データベース接続プール初期化完了（フォールバック）")
            except Exception as e2:
                app.logger.error(f"フォールバック接続プール初期化エラー: {e2}")

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
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
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
def check_stage_completion(user_id, source, stage, page_range, difficulty):
    """指定ステージが完了しているかチェック（キャッシュ付き）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
                
                # 完了済みチャンク数を取得
                cur.execute('''
                    SELECT COUNT(*) FROM chunk_progress 
                    WHERE user_id = %s AND source = %s AND stage = %s 
                    AND page_range = %s AND difficulty = %s AND completed = true
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
                        chunk_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        
                        if chunk_cards:
                            chunk_card_ids = [card['id'] for card in chunk_cards]
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
        chunk_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
        
        if not chunk_cards:
            return []
        
        chunk_card_ids = [card['id'] for card in chunk_cards]
        
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

def get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty):
    """全ステージの詳細進捗情報を取得（最適化版）"""
    stages_info = []
    
    try:
        for stage in range(1, 4):
            stage_info = get_stage_detailed_progress(user_id, source, stage, page_range, difficulty)
            
            if stage_info:
                stages_info.append(stage_info)
                if not stage_info.get('stage_completed', False):
                    break
            else:
                break
                
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
            # Stage 1完了チェック
            stage1_completed = check_stage_completion(user_id, source, 1, page_range, difficulty)
            if not stage1_completed:
                app.logger.warning(f"[STAGE_PROGRESS] Stage1未完了のためStage2は表示しない")
                return None
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            target_cards = []
        
        if not target_cards:
            app.logger.debug(f"[STAGE_PROGRESS] Stage{stage}: 対象カードなし")
            return None
        
        subject = target_cards[0]['subject']
        
        if stage == 1:
            chunks = create_chunks_for_cards(target_cards, subject)
            total_chunks = len(chunks)
        else:
            chunks = [target_cards]
            total_chunks = 1
        
        # 各チャンクの進捗を取得
        chunks_progress = []
        stage_completed = True
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for chunk_num in range(1, total_chunks + 1):
                    if stage == 1:
                        chunk_cards = chunks[chunk_num - 1]
                    else:
                        chunk_cards = target_cards
                    
                    chunk_card_ids = [card['id'] for card in chunk_cards]
                    
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
                    cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
                    user = cur.fetchone()

            if user and check_password_hash(user[2], password):
                login_user(User(user[0], user[1]))
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
                        cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
                        user = cur.fetchone()

                if user and check_password_hash(user[2], password):
                    login_user(User(user[0], user[1]))
                    return redirect(url_for('dashboard'))
                else:
                    flash("ログインに失敗しました。")
            except Exception as e:
                app.logger.error(f"ログインエラー: {e}")
                flash("ログイン中にエラーが発生しました")
    
    if current_user.is_authenticated:
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
        if not saved_page_range:
            flash("学習設定が必要です。ページ範囲と難易度を設定してください。")
            return redirect(url_for('dashboard'))

        # 詳細進捗情報を取得
        stages_info = get_detailed_progress_for_all_stages(user_id, source, saved_page_range, saved_difficulty)
        
        if not stages_info:
            stages_info = create_fallback_stage_info(source, saved_page_range, saved_difficulty, user_id)

        return render_template(
            'prepare.html',
            source=source,
            full_material_name=full_material_name,
            stages_info=stages_info,
            saved_page_range=saved_page_range,
            saved_difficulty=saved_difficulty
        )
        
    except Exception as e:
        app.logger.error(f"準備画面エラー: {e}")
        flash("準備画面でエラーが発生しました")
        return redirect(url_for('dashboard'))

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
    """学習実行画面（最適化版）"""
    try:
        session['current_source'] = source
        
        mode = session.get('mode', 'test')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        stage = session.get('stage', 1)
        user_id = str(current_user.id)

        # Stage 1の処理
        if stage == 1:
            try:
                chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
            except Exception as e:
                app.logger.error(f"チャンク進捗取得エラー: {e}")
                flash("チャンク進捗の取得に失敗しました。")
                return redirect(url_for('prepare', source=source))
            
            if not chunk_progress:
                flash("該当するカードが見つかりませんでした。")
                return redirect(url_for('prepare', source=source))
            
            # テストモード完了時は常にprepare画面に戻る（継続なし）
            if chunk_progress.get('all_completed') and mode != 'chunk_practice':
                flash("🏆 Stage 1の全チャンクが完了しました！")
                return redirect(url_for('prepare', source=source))
            
            if mode == 'chunk_practice':
                current_chunk = session.get('practicing_chunk')
                cards_dict = get_chunk_practice_cards(user_id, source, stage, current_chunk, page_range, difficulty)
                
                # 練習カードがない場合のみprepare画面に戻る
                if not cards_dict:
                    flash(f"✅ チャンク{current_chunk}の練習完了！")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('prepare', source=source))
                
                total_chunks = chunk_progress['total_chunks']
                app.logger.info(f"[PRACTICE] チャンク{current_chunk}: {len(cards_dict)}問の練習継続")
            else:
                current_chunk = chunk_progress['current_chunk']
                total_chunks = chunk_progress['total_chunks']
                
                if current_chunk is None:
                    flash("🏆 Stage 1の全チャンクが完了しました！")
                    return redirect(url_for('prepare', source=source))
                
                session['current_chunk'] = current_chunk
                cards_dict = get_study_cards_fast(source, stage, mode, page_range, user_id, difficulty, current_chunk)
        
        # ステージ2・3の処理
        elif stage in [2, 3]:
            try:
                chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
            except Exception as e:
                app.logger.error(f"Stage {stage}チャンク進捗エラー: {e}")
                chunk_progress = None
            
            if not chunk_progress:
                flash(f"Stage {stage}で学習する×問題がありません。")
                return redirect(url_for('prepare', source=source))
            
            if chunk_progress.get('all_completed'):
                flash(f"🏆 Stage {stage}の全チャンクが完了しました！")
                return redirect(url_for('prepare', source=source))
            
            # 練習モードの継続処理
            if mode == 'practice':
                current_chunk = session.get('practicing_chunk', 1)
                cards_dict = get_chunk_practice_cards_universal(user_id, source, stage, current_chunk, page_range, difficulty)
                
                # 練習カードがない場合のみprepare画面に戻る
                if not cards_dict:
                    flash(f"✅ Stage {stage}の練習完了！すべての×問題を克服しました。")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('prepare', source=source))
                
                total_chunks = chunk_progress['total_chunks']
                app.logger.info(f"[STAGE{stage}_PRACTICE] 練習カード{len(cards_dict)}問を継続表示")
            else:
                # テストモード
                current_chunk = chunk_progress['current_chunk']
                total_chunks = chunk_progress['total_chunks']
                
                if current_chunk is None:
                    flash(f"🏆 Stage {stage}の全チャンクが完了しました！")
                    return redirect(url_for('prepare', source=source))
                
                if stage == 2:
                    cards_dict = get_stage2_cards(source, page_range, user_id, difficulty)
                else:
                    cards_dict = get_stage3_cards(source, page_range, user_id, difficulty)
        
        else:
            cards_dict = []
            current_chunk = None
            total_chunks = 1

        if not cards_dict:
            if stage in [2, 3]:
                flash(f"Stage {stage}で学習する×問題がありません。")
            else:
                flash("該当するカードが見つかりませんでした。")
            return redirect(url_for('prepare', source=source))

        return render_template('index.html',
                             cards=cards_dict, 
                             mode=mode,
                             current_chunk=current_chunk,
                             total_chunks=total_chunks,
                             stage=stage,
                             source=source)

    except Exception as e:
        app.logger.error(f"学習画面エラー: {e}")
        flash("学習開始でエラーが発生しました")
        return redirect(url_for('prepare', source=source))

# ========== Redis除去版 パート13: ログ記録とデバッグルート（最終パート） ==========

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    """シンプル化されたログ記録（練習モードは常にprepare画面に戻る）"""
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = data.get('stage')
    mode = data.get('mode')
    user_id = str(current_user.id)

    session_mode = session.get('mode', mode)
    log_mode = 'chunk_practice' if session_mode == 'chunk_practice' else mode

    # 即座にレスポンスを返す準備
    response_data = {'status': 'ok'}
    
    try:
        # ログを非同期キューに追加（ノンブロッキング）
        log_queue.put((user_id, card_id, result, stage, log_mode), block=False)
        
        # キャッシュクリアも非同期で実行
        threading.Thread(
            target=clear_user_cache, 
            args=(user_id, session.get('current_source')), 
            daemon=True
        ).start()
        
        # 🚀 練習モードは常にprepare画面に戻る（シンプル化）
        if session_mode in ['practice', 'chunk_practice']:
            response_data.update({
                'practice_completed': True,
                'message': "✅ 練習ラウンド完了！",
                'redirect_to_prepare': True
            })
            app.logger.info(f"🎯 練習モード完了: Stage{stage} → prepare画面へ")
            return jsonify(response_data)
        
        # 以下はテストモードの処理（既存のまま）
        source = session.get('current_source')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        # ステージ1のチャンクテスト完了時
        if stage == 1 and session_mode == 'test':
            current_chunk = session.get('current_chunk', 1)
            
            if source:
                try:
                    chunk_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty, current_chunk)
                    
                    if chunk_cards:
                        chunk_card_ids = [card['id'] for card in chunk_cards]
                        
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute('''
                                    SELECT COUNT(DISTINCT card_id)
                                    FROM study_log
                                    WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                                ''', (user_id, stage, chunk_card_ids))
                                tested_count = cur.fetchone()[0]
                    
                        # テスト完了時は常にprepare画面に戻る
                        if tested_count >= len(chunk_card_ids):
                            practice_cards = get_chunk_practice_cards(user_id, source, stage, current_chunk, page_range, difficulty)
                            
                            if practice_cards:
                                response_data.update({
                                    'chunk_test_completed': True,
                                    'has_wrong_answers': True,
                                    'completed_chunk': current_chunk,
                                    'practice_cards_count': len(practice_cards),
                                    'message': f"🎉 チャンク{current_chunk}テスト完了！間違えた問題を練習してください。",
                                    'redirect_to_prepare': True
                                })
                            else:
                                response_data.update({
                                    'chunk_test_completed': True,
                                    'has_wrong_answers': False,
                                    'completed_chunk': current_chunk,
                                    'message': f"🌟 チャンク{current_chunk}完了！全問正解です。",
                                    'redirect_to_prepare': True
                                })
                            
                except Exception as e:
                    app.logger.error(f"チャンク完了チェックエラー: {e}")
        
        # ステージ2・3のテストモード完了チェック
        elif stage in [2, 3] and session_mode == 'test':
            if source:
                try:
                    if stage == 2:
                        target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
                    else:
                        target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
                    
                    if target_cards:
                        target_card_ids = [card['id'] for card in target_cards]
                        
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute('''
                                    SELECT COUNT(DISTINCT card_id)
                                    FROM study_log
                                    WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                                ''', (user_id, stage, target_card_ids))
                                tested_count = cur.fetchone()[0]
                    
                        if tested_count >= len(target_card_ids):
                            practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, 1, page_range, difficulty)
                            
                            if practice_cards:
                                response_data.update({
                                    'stage_test_completed': True,
                                    'has_wrong_answers': True,
                                    'completed_stage': stage,
                                    'practice_cards_count': len(practice_cards),
                                    'message': f"🎉 ステージ{stage}テスト完了！間違えた問題を練習してください。",
                                    'redirect_to_prepare': True
                                })
                            else:
                                response_data.update({
                                    'stage_test_completed': True,
                                    'has_wrong_answers': False,
                                    'completed_stage': stage,
                                    'message': f"🌟 ステージ{stage}完了！全問正解です。",
                                    'redirect_to_prepare': True
                                })
                        
                except Exception as e:
                    app.logger.error(f"ステージ{stage}テスト完了チェックエラー: {e}")
        
        return jsonify(response_data)
        
    except queue.Full:
        app.logger.error("ログキューが満杯です")
        return jsonify({'status': 'error', 'message': 'システムが混雑しています'}), 503
    except Exception as e:
        app.logger.error(f"高速ログエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/debug_cards/<source>')
@login_required
def debug_cards(source):
    """デバッグ用: カード取得状況を確認"""
    user_id = str(current_user.id)
    page_range = session.get('page_range', '').strip()
    difficulty = session.get('difficulty', '').strip()
    stage = session.get('stage', 1)
    
    try:
        # Stage 1のカード取得テスト
        stage1_cards = get_study_cards_fast(source, 1, 'test', page_range, user_id, difficulty, 1)
        
        # Stage 2のカード取得テスト
        stage2_cards = get_stage2_cards(source, page_range, user_id, difficulty) if stage >= 2 else []
        
        # Stage 3のカード取得テスト  
        stage3_cards = get_stage3_cards(source, page_range, user_id, difficulty) if stage >= 3 else []
        
        debug_info = {
            'source': source,
            'page_range': page_range,
            'difficulty': difficulty,
            'stage': stage,
            'user_id': user_id,
            'stage1_cards_count': len(stage1_cards) if stage1_cards else 0,
            'stage2_cards_count': len(stage2_cards) if stage2_cards else 0,
            'stage3_cards_count': len(stage3_cards) if stage3_cards else 0,
            'stage1_cards': stage1_cards[:3] if stage1_cards else [],  # 最初の3件
            'stage2_cards': stage2_cards[:3] if stage2_cards else [],
            'stage3_cards': stage3_cards[:3] if stage3_cards else []
        }
        
        return f"<pre>{str(debug_info)}</pre>"
        
    except Exception as e:
        return f"<pre>エラー: {str(e)}</pre>"

@app.route('/reset_history/<source>', methods=['POST'])
@login_required
def reset_history(source):
    """学習履歴リセット（最適化版）"""
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    DELETE FROM study_log
                    WHERE user_id = %s AND card_id IN (
                        SELECT id FROM image WHERE source = %s
                    )
                ''', (user_id, source))
                
                cur.execute('''
                    DELETE FROM chunk_progress
                    WHERE user_id = %s AND source = %s
                ''', (user_id, source))
                
                conn.commit()
        
        # キャッシュクリア（履歴リセット時）
        clear_user_cache(user_id, source)
        
        flash(f"{source} の学習履歴を削除しました。")
    except Exception as e:
        app.logger.error(f"履歴削除エラー: {e}")
        flash("履歴の削除に失敗しました。")

    return redirect(url_for('dashboard'))

@app.route('/images_batch/<source>')
@login_required
def get_images_batch(source):
    """画像バッチ取得（練習モード特殊処理を削除してシンプル化）"""
    try:
        user_id = str(current_user.id)
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        stage = session.get('stage', 1)
        mode = session.get('mode', 'test')
        
        # テストモードのみの処理（練習モードの特殊処理は削除）
        if stage == 1:
            chunk_number = session.get('current_chunk', 1)
            cards = get_study_cards_fast(source, stage, mode, page_range, user_id, difficulty, chunk_number)
        elif stage == 2:
            cards = get_stage2_cards(source, page_range, user_id, difficulty)
        else:
            cards = get_stage3_cards(source, page_range, user_id, difficulty)
        
        # 最大5枚まで返す
        batch_data = []
        for card in (cards or [])[:5]:
            batch_data.append({
                'id': card['id'],
                'image_problem': card['image_problem'],
                'image_answer': card['image_answer'],
                'page_number': card['page_number'],
                'problem_number': card['problem_number'],
                'level': card['level']
            })
        
        return jsonify({'cards': batch_data})
        
    except Exception as e:
        app.logger.error(f"バッチ画像取得エラー: {e}")
        return jsonify({'error': 'Batch fetch error'}), 500

# ========== アプリケーション起動とクリーンアップ ==========

def cleanup_workers():
    """アプリ終了時のワーカークリーンアップ"""
    global log_worker_active
    log_worker_active = False
    try:
        log_queue.put(None, timeout=1)  # 終了シグナル
        if log_thread.is_alive():
            log_thread.join(timeout=2)
        app.logger.info("🧹 ワーカークリーンアップ完了")
    except Exception as e:
        app.logger.error(f"クリーンアップエラー: {e}")

def cleanup_db_pool():
    """アプリ終了時のDB接続プール削除"""
    global db_pool
    if db_pool:
        try:
            db_pool.closeall()
            app.logger.info("🧹 DB接続プール削除完了")
        except Exception as e:
            app.logger.error(f"DB接続プール削除エラー: {e}")

# 終了時の処理を登録
atexit.register(cleanup_workers)
atexit.register(cleanup_db_pool)

if __name__ == '__main__':
    init_connection_pool()
    threading.Thread(target=optimize_database_indexes, daemon=True).start()
    
    print("⚡ 超高速化版暗記アプリ起動完了")
    
    # Render用のポート設定
    port = int(os.environ.get('PORT', 10000))
    # 本番環境では0.0.0.0にバインド
    host = '0.0.0.0'
    app.run(host=host, port=port, threaded=True)