# ========== app.py パート1: 基本設定とインポート ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import math
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import redis
from functools import wraps
import json
import hashlib
import threading
import time

# ========== 設定エリア ==========
load_dotenv(dotenv_path='dbname.env')

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
logging.basicConfig(level=logging.DEBUG)

# Flask-Login 初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# DB接続情報
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# 🔥 Redis高速キャッシュ設定
try:
    redis_client = redis.Redis(
        host='localhost', port=6379, db=0, decode_responses=True,
        socket_connect_timeout=5, socket_timeout=5
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("🚀 Redis接続成功 - 高速モード有効")
except Exception as e:
    REDIS_AVAILABLE = False
    redis_client = None
    print(f"⚠️ Redis接続失敗 (フォールバックモード): {e}")

# 🔥 接続プール初期化（パフォーマンス大幅向上）
connection_pool = None
pool_lock = threading.Lock()

def init_connection_pool():
    """接続プールを初期化"""
    global connection_pool
    try:
        connection_pool = SimpleConnectionPool(
            minconn=2,
            maxconn=20,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        app.logger.info("📊 データベース接続プール初期化完了")
        
        # データベースインデックス最適化
        optimize_database_indexes()
        
    except Exception as e:
        app.logger.error(f"接続プール初期化エラー: {e}")

def get_db_connection():
    """接続プールから接続を取得（高速化）"""
    if connection_pool:
        try:
            with pool_lock:
                return connection_pool.getconn()
        except Exception as e:
            app.logger.error(f"プール接続エラー: {e}")
    
    # フォールバック：直接接続
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def return_db_connection(conn):
    """接続をプールに返却"""
    if connection_pool and conn:
        try:
            with pool_lock:
                connection_pool.putconn(conn)
        except Exception as e:
            app.logger.error(f"接続返却エラー: {e}")
            try:
                conn.close()
            except:
                pass

# ========== app.py パート2: データベース最適化とキャッシュ ==========

def optimize_database_indexes():
    """🔥 データベースインデックス最適化（超高速化）"""
    indexes = [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_study_log_user_stage_mode ON study_log(user_id, stage, mode);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_study_log_composite ON study_log(user_id, stage, mode, card_id, id DESC);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_image_source_page ON image(source, page_number);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_image_source_level ON image(source, level);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_progress_user_source_stage ON chunk_progress(user_id, source, stage);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_study_log_card_result ON study_log(card_id, result, id DESC);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_settings_user_source ON user_settings(user_id, source);"
    ]
    
    success_count = 0
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for index_sql in indexes:
            try:
                cur.execute(index_sql)
                conn.commit()
                success_count += 1
            except Exception as e:
                if "already exists" not in str(e):
                    app.logger.error(f"インデックス作成エラー: {e}")
                conn.rollback()
        
        cur.close()
        return_db_connection(conn)
        
        app.logger.info(f"📊 データベース最適化完了: {success_count}個のインデックス")
    except Exception as e:
        app.logger.error(f"データベース最適化エラー: {e}")

# 🔥 高速キャッシュシステム
def cache_key(*args):
    """キャッシュキー生成"""
    key_string = "_".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

def smart_cache(expire_time=180):
    """スマートキャッシュデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not REDIS_AVAILABLE:
                return func(*args, **kwargs)
            
            key = f"{func.__name__}_{cache_key(*args, *kwargs.values())}"
            
            try:
                cached_result = redis_client.get(key)
                if cached_result:
                    return json.loads(cached_result)
            except:
                pass
            
            result = func(*args, **kwargs)
            
            try:
                redis_client.setex(key, expire_time, json.dumps(result, default=str))
            except:
                pass
            
            return result
        return wrapper
    return decorator

def clear_user_cache(user_id, source=None):
    """ユーザーキャッシュクリア"""
    if not REDIS_AVAILABLE:
        return
    
    try:
        pattern = f"*{user_id}*"
        if source:
            pattern = f"*{user_id}*{source}*"
        
        deleted_count = 0
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
            deleted_count += 1
        
        if deleted_count > 0:
            app.logger.info(f"🗑️ キャッシュクリア: {deleted_count}件")
    except:
        pass

# 🔥 超高速ログ記録システム
def log_result_turbo(user_id, card_id, result, stage, mode):
    """超高速ログ記録"""
    log_data = {
        'user_id': user_id,
        'card_id': card_id,
        'result': result,
        'stage': stage,
        'mode': mode,
        'timestamp': datetime.now().isoformat()
    }
    
    if REDIS_AVAILABLE:
        try:
            redis_client.lpush('study_log_queue', json.dumps(log_data))
            queue_length = redis_client.llen('study_log_queue')
            if queue_length >= 5:  # バッチサイズ調整
                threading.Thread(target=process_log_batch, daemon=True).start()
            return True
        except:
            pass
    
    # フォールバック：直接DB書き込み
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO study_log (user_id, card_id, result, stage, mode)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, card_id, result, stage, mode))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        return True
    except Exception as e:
        app.logger.error(f"ログ記録エラー: {e}")
        return False

def process_log_batch():
    """バッチログ処理（高速化）"""
    if not REDIS_AVAILABLE:
        return
    
    try:
        logs = []
        for _ in range(15):  # バッチサイズ
            log_json = redis_client.rpop('study_log_queue')
            if not log_json:
                break
            logs.append(json.loads(log_json))
        
        if logs:
            conn = get_db_connection()
            cur = conn.cursor()
            
            values = [(log['user_id'], log['card_id'], log['result'], 
                      log['stage'], log['mode']) for log in logs]
            
            cur.executemany('''
                INSERT INTO study_log (user_id, card_id, result, stage, mode)
                VALUES (%s, %s, %s, %s, %s)
            ''', values)
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
            app.logger.info(f"⚡ バッチログ処理: {len(logs)}件完了")
    except Exception as e:
        app.logger.error(f"バッチ処理エラー: {e}")

def background_worker():
    """バックグラウンドでログ処理"""
    while True:
        try:
            if REDIS_AVAILABLE:
                queue_length = redis_client.llen('study_log_queue')
                if queue_length > 0:
                    process_log_batch()
            time.sleep(0.5)
        except Exception as e:
            app.logger.error(f"バックグラウンドエラー: {e}")
            time.sleep(2)

# ========== app.py パート3: 基本ユーティリティとUser関連 ==========

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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        if user:
            return User(*user)
    except Exception as e:
        app.logger.error(f"ユーザー読み込みエラー: {e}")
    return None

# ========== 学習履歴チェック関数 ==========

@smart_cache(expire_time=300)
def has_study_history(user_id, source):
    """指定教材に学習履歴があるかチェック（キャッシュ付き）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(*) FROM study_log sl
            JOIN image i ON sl.card_id = i.id
            WHERE sl.user_id = %s AND i.source = %s
        ''', (user_id, source))
        count = cur.fetchone()[0]
        cur.close()
        return_db_connection(conn)
        return count > 0
    except Exception as e:
        app.logger.error(f"学習履歴チェックエラー: {e}")
        return False

@smart_cache(expire_time=120)
def check_stage_completion(user_id, source, stage, page_range, difficulty):
    """指定ステージが完了しているかチェック（キャッシュ付き）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT completed FROM chunk_progress 
            WHERE user_id = %s AND source = %s AND stage = %s AND completed = true
        ''', (user_id, source, stage))
        completed_chunks = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        
        if completed_chunks:
            app.logger.debug(f"[STAGE_CHECK] Stage{stage}完了済み")
            return True
        else:
            app.logger.debug(f"[STAGE_CHECK] Stage{stage}未完了")
            return False
            
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

# ========== app.py パート4: カード取得関数群 ==========

@smart_cache(expire_time=120)
def get_study_cards(source, stage, mode, page_range, user_id, difficulty='', chunk_number=None):
    """統合復習対応版のget_study_cards（キャッシュ付き高速化）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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

        # Stage・モード別の条件
        if mode == 'test':
            if stage == 1:
                pass  # チャンク分割は後で行う
            elif stage == 2:
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
            elif stage == 3:
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

        query += ' ORDER BY id DESC'
        cur.execute(query, params)
        records = cur.fetchall()
        cur.close()
        return_db_connection(conn)

        cards_dict = [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]

        # Stage 1のみチャンク分割処理
        if stage == 1 and chunk_number and cards_dict:
            subject = cards_dict[0]['subject']
            chunks = create_chunks_for_cards(cards_dict, subject)
            
            if 1 <= chunk_number <= len(chunks):
                return chunks[chunk_number - 1]
            else:
                return []
        
        return cards_dict
        
    except Exception as e:
        app.logger.error(f"教材取得エラー: {e}")
        return None

@smart_cache(expire_time=120)
def get_stage2_cards(source, page_range, user_id, difficulty):
    """Stage 2: Stage 1の×問題を全て取得（キャッシュ付き）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        cur.close()
        return_db_connection(conn)

        return [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]
        
    except Exception as e:
        app.logger.error(f"Stage 2カード取得エラー: {e}")
        return []

@smart_cache(expire_time=120)
def get_stage3_cards(source, page_range, user_id, difficulty):
    """Stage 3: Stage 2の×問題を全て取得（キャッシュ付き）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        cur.close()
        return_db_connection(conn)

        return [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]
        
    except Exception as e:
        app.logger.error(f"Stage 3カード取得エラー: {e}")
        return []

# ========== app.py パート5: チャンク進捗管理関数群 ==========

def get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty):
    """Stage 1用のチャンク進捗を取得または作成（最適化版）"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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
                chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                
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
                
                cur.close()
                return_db_connection(conn)
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
                
                cur.close()
                return_db_connection(conn)
                return result
        else:
            # 新規作成
            cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
            
            if not cards:
                cur.close()
                return_db_connection(conn)
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
            cur.close()
            return_db_connection(conn)
            
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
        
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        
        cur.close()
        return_db_connection(conn)
        
        app.logger.debug(f"[Universal進捗] Stage{stage}完了: {result}")
        return result
            
    except Exception as e:
        app.logger.error(f"[Universal進捗] Stage{stage}エラー: {e}")
        import traceback
        app.logger.error(f"[Universal進捗] トレースバック: {traceback.format_exc()}")
        return None
    
# ========== app.py パート6: 練習問題取得関数群 ==========

def get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty):
    """Stage 1用の指定チャンクの練習問題を取得（最適化版）"""
    try:
        chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
        
        if not chunk_cards:
            return []
        
        chunk_card_ids = [card['id'] for card in chunk_cards]
        
        conn = get_db_connection()
        cur = conn.cursor()
        
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
            cur.close()
            return_db_connection(conn)
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
            cur.close()
            return_db_connection(conn)
            return []
        
        # 練習対象のカード詳細を取得
        cur.execute('''
            SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
            FROM image
            WHERE id = ANY(%s)
            ORDER BY id
        ''', (need_practice_ids,))
        
        records = cur.fetchall()
        cur.close()
        return_db_connection(conn)
        
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
        
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        cur.close()
        return_db_connection(conn)
        
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
        cards = get_study_cards(source, 1, 'test', page_range, user_id, difficulty)
        
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

# ========== app.py パート7: ステージ詳細進捗関数 ==========

def get_stage_detailed_progress(user_id, source, stage, page_range, difficulty):
    """指定ステージの詳細進捗を取得（エラーハンドリング強化版）"""
    try:
        # Stage 3の前提条件チェック
        if stage == 3:
            stage2_completed = check_stage_completion(user_id, source, 2, page_range, difficulty)
            if not stage2_completed:
                app.logger.warning(f"[STAGE_PROGRESS] Stage2未完了のためStage3は表示しない")
                return None
        
        # ステージ別の対象カードを取得
        if stage == 1:
            target_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
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
        
        # 以下は既存のロジックと同じ...
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
        
        conn = get_db_connection()
        cur = conn.cursor()
        
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
            practice_completed = True
            
            if test_wrong_cards:
                practice_correct_cards = [cid for cid, result in practice_results.items() if result == 'known']
                practice_completed = len(set(test_wrong_cards) & set(practice_correct_cards)) == len(test_wrong_cards)
            
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
                'chunk_completed': chunk_completed,
                'can_start_test': can_start_test,
                'can_start_practice': test_completed and len(test_wrong_cards) > 0
            }
            
            chunks_progress.append(chunk_progress)
        
        cur.close()
        return_db_connection(conn)
        
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

# ========== app.py パート8: ルート定義（認証系） ==========

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            return_db_connection(conn)

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
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password))
            conn.commit()
            cur.close()
            return_db_connection(conn)
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"登録エラー: {e}")

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        
        cur.close()
        return_db_connection(conn)
        
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO user_settings (user_id, source, page_range, difficulty)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, source)
            DO UPDATE SET page_range = EXCLUDED.page_range, difficulty = EXCLUDED.difficulty
        ''', (user_id, source, page_range, difficulty))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # キャッシュクリア（設定変更時）
        clear_user_cache(user_id, source)
        
        flash("✅ 設定を保存しました。")
    except Exception as e:
        app.logger.error(f"user_settings保存エラー: {e}")
        flash("❌ 設定の保存に失敗しました")
    
    return redirect(url_for('prepare', source=source))

# ========== app.py パート10: 学習実行ルート ==========

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
                cards_dict = get_study_cards(source, stage, mode, page_range, user_id, difficulty, current_chunk)
        
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

# ========== app.py パート11: ログ記録とデバッグルート（最終パート） ==========

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    """学習結果記録ルート（超高速化版）"""
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = data.get('stage')
    mode = data.get('mode')
    user_id = str(current_user.id)

    session_mode = session.get('mode', mode)
    log_mode = 'chunk_practice' if session_mode == 'chunk_practice' else mode

    # 🔥 超高速ログ記録を使用
    success = log_result_turbo(user_id, card_id, result, stage, log_mode)
    
    if not success:
        return jsonify({'status': 'error', 'message': 'ログ記録に失敗しました'}), 500

    response_data = {'status': 'ok'}
    
    # キャッシュクリア（結果記録時）
    clear_user_cache(user_id, session.get('current_source'))
    
    # ステージ1のチャンクテスト完了時（即座にprepare画面に戻る）
    if stage == 1 and session_mode == 'test':
        source = session.get('current_source')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        current_chunk = session.get('current_chunk', 1)
        
        if source:
            try:
                chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, current_chunk)
                
                if chunk_cards:
                    chunk_card_ids = [card['id'] for card in chunk_cards]
                    
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id)
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                    ''', (user_id, stage, chunk_card_ids))
                    tested_count = cur.fetchone()[0]
                    cur.close()
                    return_db_connection(conn)
                
                    # テスト完了時は常にprepare画面に戻る
                    if tested_count == len(chunk_card_ids):
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
    
    # ステージ1の練習モード（継続学習）
    elif stage == 1 and session_mode == 'chunk_practice':
        source = session.get('current_source')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        practicing_chunk = session.get('practicing_chunk')
        
        if source and practicing_chunk:
            try:
                # 残りの練習カードをチェック
                remaining_practice_cards = get_chunk_practice_cards(user_id, source, stage, practicing_chunk, page_range, difficulty)
                
                app.logger.info(f"[PRACTICE_LOG] チャンク{practicing_chunk}: 残り練習カード{len(remaining_practice_cards)}問")
                
                if not remaining_practice_cards:
                    # すべての練習完了時のみprepare画面に戻る
                    app.logger.info(f"[PRACTICE_LOG] チャンク{practicing_chunk}: 練習完了 - prepare画面に戻る")
                    response_data.update({
                        'practice_completed': True,
                        'completed_chunk': practicing_chunk,
                        'message': f"✅ チャンク{practicing_chunk}の練習完了！",
                        'redirect_to_prepare': True
                    })
                else:
                    # まだ練習問題が残っている場合は継続（prepare画面に戻らない）
                    app.logger.info(f"[PRACTICE_LOG] チャンク{practicing_chunk}: 練習継続 - 残り{len(remaining_practice_cards)}問")
                    response_data.update({
                        'practice_continuing': True,
                        'remaining_count': len(remaining_practice_cards),
                        'message': f"残り{len(remaining_practice_cards)}問の練習を続けます。",
                        'redirect_to_prepare': False
                    })
                    
            except Exception as e:
                app.logger.error(f"練習完了チェックエラー: {e}")
    
    # ステージ2・3のテストモード（即座にprepare画面に戻る）
    elif stage in [2, 3] and session_mode == 'test':
        source = session.get('current_source')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        if source:
            try:
                # 対象カードを取得
                if stage == 2:
                    target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
                else:
                    target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
                
                if target_cards:
                    target_card_ids = [card['id'] for card in target_cards]
                    
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id)
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                    ''', (user_id, stage, target_card_ids))
                    tested_count = cur.fetchone()[0]
                    cur.close()
                    return_db_connection(conn)
                
                    # ステージ2・3のテスト完了時は即座にprepare画面に戻る
                    if tested_count == len(target_card_ids):
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
    
    # ステージ2・3の練習モード（継続学習）
    elif stage in [2, 3] and session_mode == 'practice':
        source = session.get('current_source')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        if source:
            try:
                # 残りの練習カードをチェック
                remaining_practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, 1, page_range, difficulty)
                
                app.logger.info(f"[STAGE{stage}_PRACTICE_LOG] 残り練習カード{len(remaining_practice_cards)}問")
                
                if not remaining_practice_cards:
                    # すべての練習完了時のみprepare画面に戻る
                    app.logger.info(f"[STAGE{stage}_PRACTICE_LOG] 練習完了 - prepare画面に戻る")
                    response_data.update({
                        'practice_completed': True,
                        'completed_stage': stage,
                        'message': f"✅ ステージ{stage}の練習完了！すべての×問題を克服しました。",
                        'redirect_to_prepare': True
                    })
                else:
                    # まだ練習問題が残っている場合は継続（prepare画面に戻らない）
                    app.logger.info(f"[STAGE{stage}_PRACTICE_LOG] 練習継続 - 残り{len(remaining_practice_cards)}問")
                    response_data.update({
                        'practice_continuing': True,
                        'remaining_count': len(remaining_practice_cards),
                        'message': f"残り{len(remaining_practice_cards)}問の練習を続けます。",
                        'redirect_to_prepare': False
                    })
                    
            except Exception as e:
                app.logger.error(f"ステージ{stage}練習完了チェックエラー: {e}")
    
    return jsonify(response_data)

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
        stage1_cards = get_study_cards(source, 1, 'test', page_range, user_id, difficulty, 1)
        
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
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        cur.close()
        return_db_connection(conn)
        
        # キャッシュクリア（履歴リセット時）
        clear_user_cache(user_id, source)
        
        flash(f"{source} の学習履歴を削除しました。")
    except Exception as e:
        app.logger.error(f"履歴削除エラー: {e}")
        flash("履歴の削除に失敗しました。")

    return redirect(url_for('dashboard'))

# ========== アプリケーション起動 ==========

if __name__ == '__main__':
    # 接続プール初期化
    init_connection_pool()
    
    # バックグラウンドワーカー開始（Redis使用時のみ）
    if REDIS_AVAILABLE:
        worker_thread = threading.Thread(target=background_worker, daemon=True)
        worker_thread.start()
        print("📈 暗記アプリ最適化完了 - 高速モード")
    else:
        print("📈 暗記アプリ最適化完了 - 基本モード")
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

