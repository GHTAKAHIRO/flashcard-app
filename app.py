# ========== インポートエリア ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import logging
import math
import psycopg2
from dotenv import load_dotenv

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

# ========== ユーティリティ関数エリア ==========
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

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

def get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty):
    """指定チャンクの練習問題を取得（テストで×だった問題のみ）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # まず、このチャンクの全カードを取得
                chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
                
                if not chunk_cards:
                    return []
                
                chunk_card_ids = [card['id'] for card in chunk_cards]
                
                # このチャンクでテスト時に×だった問題のうち、まだ練習で○になっていない問題
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE id = ANY(%s)
                    AND id IN (
                        -- このチャンクのテスト×問題
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
                        -- 練習で○になった問題
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'chunk_practice'
                            AND card_id = ANY(%s)
                        ) AS practice_ranked
                        WHERE rn = 1 AND result = 'known'
                    )
                    ORDER BY id
                '''
                
                cur.execute(query, (
                    chunk_card_ids,  # 対象カードID
                    user_id, stage, chunk_card_ids,  # テスト×問題
                    user_id, stage, chunk_card_ids   # 練習○問題
                ))
                
                records = cur.fetchall()
                
                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
    except Exception as e:
        app.logger.error(f"チャンク練習問題取得エラー: {e}")
        return []
       
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

# ========== データベース関数エリア ==========
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

def get_study_cards(source, stage, mode, page_range, user_id, difficulty='', chunk_number=None):
    """統合復習対応版のget_study_cards（テスト環境用）"""
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

                # 🔥 Stage・モード別の条件（統合復習対応）
                if mode == 'test':
                    if stage == 1:
                        # Stage 1: 既存のチャンク処理
                        pass  # チャンク分割は後で行う
                    elif stage == 2:
                        # 🔥 Stage 2: 全チャンクのStage 1×問題すべて
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
                        app.logger.debug(f"[Stage 2] Stage 1の×問題を取得: user_id={user_id}")
                    elif stage == 3:
                        # 🔥 Stage 3: Stage 2の×問題すべて
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
                        app.logger.debug(f"[Stage 3] Stage 2の×問題を取得: user_id={user_id}")
                
                elif mode == 'practice':
                    # 練習モードは既存ロジック
                    if stage == 1:
                        query += '''
                            AND id IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 1 AND mode = 'test'
                                ) AS test_ranked
                                WHERE rn = 1 AND result = 'unknown'
                            )
                            AND id NOT IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 1 AND mode = 'practice'
                                ) AS practice_ranked
                                WHERE rn = 1 AND result = 'known'
                            )
                        '''
                        params.extend([user_id, user_id])
                    elif stage == 2:
                        query += '''
                            AND id IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 2 AND mode = 'test'
                                ) AS test_ranked
                                WHERE rn = 1 AND result = 'unknown'
                            )
                            AND id NOT IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 2 AND mode = 'practice'
                                ) AS practice_ranked
                                WHERE rn = 1 AND result = 'known'
                            )
                        '''
                        params.extend([user_id, user_id])
                    elif stage == 3:
                        query += '''
                            AND id IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 3 AND mode = 'test'
                                ) AS test_ranked
                                WHERE rn = 1 AND result = 'unknown'
                            )
                            AND id NOT IN (
                                SELECT card_id FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = 3 AND mode = 'practice'
                                ) AS practice_ranked
                                WHERE rn = 1 AND result = 'known'
                            )
                        '''
                        params.extend([user_id, user_id])

                query += ' ORDER BY id DESC'
                
                app.logger.debug(f"[統合復習] クエリ実行: stage={stage}, mode={mode}, params={params}")
                cur.execute(query, params)
                records = cur.fetchall()
                app.logger.debug(f"[統合復習] 取得件数: {len(records)}件")

        cards_dict = [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]

        # 🔥 Stage 1のみチャンク分割処理
        if stage == 1 and chunk_number and cards_dict:
            subject = cards_dict[0]['subject']
            chunks = create_chunks_for_cards(cards_dict, subject)
            
            app.logger.debug(f"[チャンク分割] stage={stage}, chunk_number={chunk_number}, 総チャンク数={len(chunks)}")
            
            if 1 <= chunk_number <= len(chunks):
                return chunks[chunk_number - 1]
            else:
                return []
        
        # 🔥 Stage 2・3は全問題をそのまま返す（チャンク分割しない）
        app.logger.debug(f"[統合復習] stage={stage}で{len(cards_dict)}問を返す")
        return cards_dict
        
    except Exception as e:
        app.logger.error(f"統合復習教材取得エラー: {e}")
        return None
    
def get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty):
    """チャンク進捗を取得または作成"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # まず既存の進捗をチェック
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
                        # このチャンクの問題を取得
                        chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        
                        if chunk_cards:
                            # このチャンクの全問題が完了しているかチェック
                            chunk_card_ids = [card['id'] for card in chunk_cards]
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id)
                                FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = %s AND card_id = ANY(%s)
                            ''', (user_id, stage, 'test', chunk_card_ids))
                            completed_count = cur.fetchone()[0]
                            
                            # 全問題完了していればチャンクを完了としてマーク
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
                    
                    # 新しく完了したチャンクがあるかチェック
                    newly_completed = set(completed_chunks_after) - set(completed_chunks_before)
                    
                    if len(completed_chunks_after) < total_chunks:
                        # 次の未完了チャンクを返す
                        next_chunk = len(completed_chunks_after) + 1
                        
                        # 新しく完了したチャンクがあれば即時復習フラグを設定
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
                        # 全チャンク完了
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
                    # 新規作成が必要
                    cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
                    
                    if not cards:
                        return None
                    
                    # 科目を取得（最初のカードから）
                    subject = cards[0]['subject']
                    chunk_size = get_chunk_size_by_subject(subject)
                    total_chunks = math.ceil(len(cards) / chunk_size)
                    
                    # chunk_progress レコードを作成
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

def get_or_create_chunk_progress_fixed_v2(user_id, source, stage, page_range, difficulty):
    """即時練習機能を含むチャンク進捗取得（修正版）"""
    try:
        app.logger.debug(f"[チャンク進捗DEBUG] 開始: user_id={user_id}, source={source}, stage={stage}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # まず既存の進捗をチェック
                cur.execute('''
                    SELECT chunk_number, total_chunks, completed 
                    FROM chunk_progress 
                    WHERE user_id = %s AND source = %s AND stage = %s
                    ORDER BY chunk_number
                ''', (user_id, source, stage))
                existing_chunks = cur.fetchall()
                
                app.logger.debug(f"[チャンク進捗DEBUG] 既存チャンク情報: {existing_chunks}")
                
                if existing_chunks:
                    total_chunks = existing_chunks[0][1]
                    completed_chunks_before = [chunk[0] for chunk in existing_chunks if chunk[2]]
                    
                    app.logger.debug(f"[チャンク進捗DEBUG] 処理前完了チャンク: {completed_chunks_before}/{total_chunks}")
                    
                    # 🔥 新しく完了するチャンクを検知するための変数
                    newly_completed_chunks = []
                    
                    # 各チャンクの完了状況をチェック・更新
                    for chunk_num in range(1, total_chunks + 1):
                        app.logger.debug(f"[チャンク進捗DEBUG] チャンク{chunk_num}をチェック中...")
                        
                        # 🔥 このチャンクが処理前に完了済みかチェック
                        was_completed_before = chunk_num in completed_chunks_before
                        
                        # このチャンクの問題を取得
                        chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        
                        if chunk_cards:
                            # このチャンクの全問題が完了しているかチェック
                            chunk_card_ids = [card['id'] for card in chunk_cards]
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id)
                                FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = %s AND card_id = ANY(%s)
                            ''', (user_id, stage, 'test', chunk_card_ids))
                            completed_count = cur.fetchone()[0]
                            
                            app.logger.debug(f"[チャンク進捗DEBUG] チャンク{chunk_num}: {completed_count}/{len(chunk_card_ids)}問完了, 処理前完了済み={was_completed_before}")
                            
                            # 全問題完了している かつ 処理前は未完了だった場合
                            if completed_count == len(chunk_card_ids) and not was_completed_before:
                                app.logger.debug(f"[チャンク進捗DEBUG] 🚀 チャンク{chunk_num}が新しく完了！")
                                
                                # DBを更新
                                cur.execute('''
                                    UPDATE chunk_progress 
                                    SET completed = true, completed_at = CURRENT_TIMESTAMP
                                    WHERE user_id = %s AND source = %s AND stage = %s AND chunk_number = %s AND completed = false
                                ''', (user_id, source, stage, chunk_num))
                                
                                updated_rows = cur.rowcount
                                app.logger.debug(f"[チャンク進捗DEBUG] チャンク{chunk_num}のDB更新結果: {updated_rows}行更新")
                                
                                # 🔥 新しく完了したチャンクとして記録
                                newly_completed_chunks.append(chunk_num)
                                
                            elif completed_count == len(chunk_card_ids) and was_completed_before:
                                app.logger.debug(f"[チャンク進捗DEBUG] チャンク{chunk_num}は既に完了済み")
                    
                    conn.commit()
                    app.logger.debug(f"[チャンク進捗DEBUG] DB更新をコミット")
                    
                    # 完了済みチャンクを再取得
                    cur.execute('''
                        SELECT chunk_number FROM chunk_progress 
                        WHERE user_id = %s AND source = %s AND stage = %s AND completed = true
                        ORDER BY chunk_number
                    ''', (user_id, source, stage))
                    completed_chunks_after = [row[0] for row in cur.fetchall()]
                    
                    app.logger.debug(f"[チャンク進捗DEBUG] 処理後完了チャンク: {completed_chunks_after}")
                    app.logger.debug(f"[チャンク進捗DEBUG] 🔥 新しく完了したチャンク: {newly_completed_chunks}")
                    
                    if len(completed_chunks_after) < total_chunks:
                        # 次の未完了チャンクを返す
                        next_chunk = len(completed_chunks_after) + 1
                        
                        # 🔥 新しく完了したチャンクがあれば即時復習フラグを設定
                        result = {
                            'current_chunk': next_chunk,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after
                        }
                        
                        if newly_completed_chunks:
                            newly_completed_chunk = max(newly_completed_chunks)
                            result['newly_completed_chunk'] = newly_completed_chunk
                            result['needs_immediate_practice'] = True
                            app.logger.debug(f"[チャンク進捗DEBUG] 🚀 即時練習フラグON: チャンク{newly_completed_chunk}")
                        else:
                            result['needs_immediate_practice'] = False
                            app.logger.debug(f"[チャンク進捗DEBUG] 即時練習フラグOFF: 新しく完了したチャンクなし")
                        
                        app.logger.debug(f"[チャンク進捗DEBUG] 返却値: {result}")
                        return result
                    else:
                        # 全チャンク完了
                        result = {
                            'current_chunk': None,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after,
                            'all_completed': True
                        }
                        
                        if newly_completed_chunks:
                            newly_completed_chunk = max(newly_completed_chunks)
                            result['newly_completed_chunk'] = newly_completed_chunk
                            result['needs_immediate_practice'] = True
                            app.logger.debug(f"[チャンク進捗DEBUG] 🚀 最終チャンクで即時練習フラグON: チャンク{newly_completed_chunk}")
                        else:
                            result['needs_immediate_practice'] = False
                            app.logger.debug(f"[チャンク進捗DEBUG] 全チャンク完了、即時練習フラグOFF")
                        
                        app.logger.debug(f"[チャンク進捗DEBUG] 全完了時の返却値: {result}")
                        return result
                else:
                    # 新規作成処理は既存のまま
                    cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
                    
                    if not cards:
                        app.logger.debug(f"[チャンク進捗DEBUG] カードが取得できません")
                        return None
                    
                    subject = cards[0]['subject']
                    chunk_size = get_chunk_size_by_subject(subject)
                    total_chunks = math.ceil(len(cards) / chunk_size)
                    
                    app.logger.debug(f"[チャンク進捗DEBUG] 新規作成: 総カード数={len(cards)}, チャンクサイズ={chunk_size}, 総チャンク数={total_chunks}")
                    
                    for chunk_num in range(1, total_chunks + 1):
                        cur.execute('''
                            INSERT INTO chunk_progress (user_id, source, stage, chunk_number, total_chunks, page_range, difficulty)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, source, stage, chunk_number) DO NOTHING
                        ''', (user_id, source, stage, chunk_num, total_chunks, page_range, difficulty))
                    
                    conn.commit()
                    app.logger.debug(f"[チャンク進捗DEBUG] 新規チャンク進捗を作成完了")
                    
                    result = {
                        'current_chunk': 1,
                        'total_chunks': total_chunks,
                        'completed_chunks': [],
                        'needs_immediate_practice': False
                    }
                    app.logger.debug(f"[チャンク進捗DEBUG] 新規作成時の返却値: {result}")
                    return result
                    
    except Exception as e:
        app.logger.error(f"[チャンク進捗DEBUG] エラー: {e}")
        app.logger.error(f"[チャンク進捗DEBUG] エラートレースバック: ", exc_info=True)
        return None
    
def get_completed_stages(user_id, source, page_range, difficulty=''):
    result = {'test': set(), 'practice': set(), 'perfect_completion': False, 'practice_history': {}}
    user_id = str(user_id)

    page_numbers = []
    if page_range:
        for part in page_range.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    page_numbers.extend([str(i) for i in range(start, end + 1)])
                except ValueError:
                    continue
            else:
                page_numbers.append(part)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                base_query = '''
                    SELECT id FROM image
                    WHERE source = %s
                '''
                base_params = [source]
                
                if page_numbers:
                    base_query += ' AND page_number::text = ANY(%s)'
                    base_params.append(page_numbers)
                
                if difficulty:
                    difficulty_list = [d.strip() for d in difficulty.split(',')]
                    difficulty_placeholders = ','.join(['%s'] * len(difficulty_list))
                    base_query += f' AND level IN ({difficulty_placeholders})'
                    base_params.extend(difficulty_list)
                
                cur.execute(base_query, base_params)
                all_card_ids = [row[0] for row in cur.fetchall()]

                for stage in [1, 2, 3]:
                    cur.execute('''
                        SELECT COUNT(*) FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'practice'
                    ''', (user_id, stage))
                    practice_count = cur.fetchone()[0]
                    result['practice_history'][stage] = practice_count > 0

                for stage in [1, 2, 3]:
                    if stage == 1:
                        target_card_ids = all_card_ids
                    elif stage == 2:
                        if 1 not in result['test']:
                            continue
                        cur.execute('''
                            SELECT card_id FROM (
                                SELECT card_id, result,
                                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                FROM study_log
                                WHERE user_id = %s AND stage = 1 AND mode = 'test'
                            ) AS ranked
                            WHERE rn = 1 AND result = 'unknown'
                        ''', (user_id,))
                        target_card_ids = [r[0] for r in cur.fetchall()]
                    elif stage == 3:
                        if 2 not in result['test']:
                            continue
                        cur.execute('''
                            SELECT card_id FROM (
                                SELECT card_id, result,
                                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                FROM study_log
                                WHERE user_id = %s AND stage = 2 AND mode = 'test'
                            ) AS ranked
                            WHERE rn = 1 AND result = 'unknown'
                        ''', (user_id,))
                        target_card_ids = [r[0] for r in cur.fetchall()]

                    if target_card_ids:
                        cur.execute('''
                            SELECT COUNT(DISTINCT card_id)
                            FROM study_log
                            WHERE user_id = %s AND mode = 'test' AND stage = %s AND card_id = ANY(%s)
                        ''', (user_id, stage, list(target_card_ids)))
                        tested_count = cur.fetchone()[0]

                        if tested_count == len(target_card_ids):
                            result['test'].add(stage)
                            
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id)
                                FROM (
                                    SELECT card_id, result,
                                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                    FROM study_log
                                    WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                                ) AS ranked
                                WHERE rn = 1 AND result = 'known'
                            ''', (user_id, stage, list(target_card_ids)))
                            perfect_count = cur.fetchone()[0]
                            
                            if perfect_count == len(target_card_ids):
                                result['perfect_completion'] = True
                                for completed_stage in range(1, stage + 1):
                                    result['practice'].add(completed_stage)
                                break

                    elif stage > 1:
                        result['test'].add(stage)
                        result['practice'].add(stage)

                if not result['perfect_completion']:
                    for stage in [1, 2, 3]:
                        if stage in result['test']:
                            if stage == 1:
                                cur.execute('''
                                    SELECT card_id FROM (
                                        SELECT card_id, result,
                                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                        FROM study_log
                                        WHERE user_id = %s AND stage = 1 AND mode = 'test'
                                    ) AS ranked
                                    WHERE rn = 1 AND result = 'unknown'
                                ''', (user_id,))
                            elif stage == 2:
                                cur.execute('''
                                    SELECT card_id FROM (
                                        SELECT card_id, result,
                                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                        FROM study_log
                                        WHERE user_id = %s AND stage = 2 AND mode = 'test'
                                    ) AS ranked
                                    WHERE rn = 1 AND result = 'unknown'
                                ''', (user_id,))
                            elif stage == 3:
                                cur.execute('''
                                    SELECT card_id FROM (
                                        SELECT card_id, result,
                                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                        FROM study_log
                                        WHERE user_id = %s AND stage = 3 AND mode = 'test'
                                    ) AS ranked
                                    WHERE rn = 1 AND result = 'unknown'
                                ''', (user_id,))
                            
                            practice_target_cards = [r[0] for r in cur.fetchall()]
                            
                            if practice_target_cards:
                                cur.execute('''
                                    SELECT card_id FROM (
                                        SELECT card_id, result,
                                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                        FROM study_log
                                        WHERE user_id = %s AND stage = %s AND mode = 'practice' AND card_id = ANY(%s)
                                    ) AS ranked
                                    WHERE rn = 1 AND result = 'known'
                                ''', (user_id, stage, practice_target_cards))
                                
                                completed_practice_cards = [r[0] for r in cur.fetchall()]
                                
                                if len(completed_practice_cards) == len(practice_target_cards):
                                    result['practice'].add(stage)
                            else:
                                result['practice'].add(stage)

    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result

def check_stage1_all_chunks_completed(user_id, source, page_range, difficulty):
    """ステージ1の全チャンク（テスト＋即時復習）が完了しているかチェック"""
    try:
        # チャンク進捗を取得
        chunk_progress = get_or_create_chunk_progress(user_id, source, 1, page_range, difficulty)
        
        if not chunk_progress:
            app.logger.debug(f"[Stage1完了判定] チャンク進捗なし")
            return False
        
        # 全チャンク完了フラグをチェック
        if chunk_progress.get('all_completed'):
            app.logger.debug(f"[Stage1完了判定] 全チャンク完了フラグ=True")
            return True
        
        # 手動で完了チェック
        completed_chunks = chunk_progress.get('completed_chunks', [])
        total_chunks = chunk_progress.get('total_chunks', 0)
        
        is_completed = len(completed_chunks) >= total_chunks
        app.logger.debug(f"[Stage1完了判定] 完了チャンク数: {len(completed_chunks)}/{total_chunks}, 完了={is_completed}")
        
        return is_completed
        
    except Exception as e:
        app.logger.error(f"Stage1完了判定エラー: {e}")
        return False

def get_completed_stages_chunk_aware(user_id, source, page_range, difficulty=''):
    """チャンク完了を考慮した完了ステージ取得"""
    result = {'test': set(), 'practice': set(), 'perfect_completion': False, 'practice_history': {}}
    user_id = str(user_id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 🔥 ステージ1の完了判定（チャンクベース）
                stage1_completed = check_stage1_all_chunks_completed(user_id, source, page_range, difficulty)
                
                if stage1_completed:
                    result['test'].add(1)
                    result['practice'].add(1)  # チャンク→即時復習完了なので練習も完了扱い
                    app.logger.debug(f"[完了ステージ] Stage1完了（チャンクベース）")
                    
                    # ステージ1完了なので、ステージ2の判定を行う
                    # ステージ1の×問題を取得（チャンク即時復習の結果は無関係）
                    base_query = '''
                        SELECT id FROM image WHERE source = %s
                    '''
                    base_params = [source]
                    
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
                        base_query += f' AND page_number IN ({placeholders})'
                        base_params.extend(page_conditions)
                    
                    # 難易度フィルタ
                    if difficulty:
                        difficulty_list = [d.strip() for d in difficulty.split(',')]
                        difficulty_placeholders = ','.join(['%s'] * len(difficulty_list))
                        base_query += f' AND level IN ({difficulty_placeholders})'
                        base_params.extend(difficulty_list)
                    
                    cur.execute(base_query, base_params)
                    all_cards = [row[0] for row in cur.fetchall()]
                    
                    if all_cards:
                        # ステージ1のテスト×問題を取得（即時復習結果は無関係）
                        cur.execute('''
                            SELECT card_id FROM (
                                SELECT card_id, result,
                                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                FROM study_log
                                WHERE user_id = %s AND stage = 1 AND mode = 'test' AND card_id = ANY(%s)
                            ) AS ranked
                            WHERE rn = 1 AND result = 'unknown'
                        ''', (user_id, all_cards))
                        stage1_wrong_cards = [row[0] for row in cur.fetchall()]
                        
                        app.logger.debug(f"[完了ステージ] Stage1×問題数: {len(stage1_wrong_cards)}")
                        
                        if not stage1_wrong_cards:
                            # ステージ1で×問題がない場合、ステージ2・3も完了
                            result['test'].add(2)
                            result['test'].add(3)
                            result['practice'].add(2)
                            result['practice'].add(3)
                            result['perfect_completion'] = True
                            app.logger.debug(f"[完了ステージ] Stage1で×問題なし、全完了")
                        else:
                            # ステージ2のテスト完了判定
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id) FROM study_log
                                WHERE user_id = %s AND stage = 2 AND mode = 'test' AND card_id = ANY(%s)
                            ''', (user_id, stage1_wrong_cards))
                            stage2_tested = cur.fetchone()[0]
                            
                            if stage2_tested == len(stage1_wrong_cards):
                                result['test'].add(2)
                                app.logger.debug(f"[完了ステージ] Stage2テスト完了")
                                
                                # ステージ3の判定
                                cur.execute('''
                                    SELECT card_id FROM (
                                        SELECT card_id, result,
                                               ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                        FROM study_log
                                        WHERE user_id = %s AND stage = 2 AND mode = 'test' AND card_id = ANY(%s)
                                    ) AS ranked
                                    WHERE rn = 1 AND result = 'unknown'
                                ''', (user_id, stage1_wrong_cards))
                                stage2_wrong_cards = [row[0] for row in cur.fetchall()]
                                
                                if not stage2_wrong_cards:
                                    result['test'].add(3)
                                    result['practice'].add(2)
                                    result['practice'].add(3)
                                    result['perfect_completion'] = True
                                    app.logger.debug(f"[完了ステージ] Stage2で×問題なし、完了")
                                else:
                                    # ステージ3のテスト判定
                                    cur.execute('''
                                        SELECT COUNT(DISTINCT card_id) FROM study_log
                                        WHERE user_id = %s AND stage = 3 AND mode = 'test' AND card_id = ANY(%s)
                                    ''', (user_id, stage2_wrong_cards))
                                    stage3_tested = cur.fetchone()[0]
                                    
                                    if stage3_tested == len(stage2_wrong_cards):
                                        result['test'].add(3)
                                        app.logger.debug(f"[完了ステージ] Stage3テスト完了")
                                        
                                        # 完全完了判定
                                        cur.execute('''
                                            SELECT COUNT(*) FROM (
                                                SELECT card_id, result,
                                                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                                FROM study_log
                                                WHERE user_id = %s AND stage = 3 AND mode = 'test' AND card_id = ANY(%s)
                                            ) AS ranked
                                            WHERE rn = 1 AND result = 'known'
                                        ''', (user_id, stage2_wrong_cards))
                                        stage3_perfect = cur.fetchone()[0]
                                        
                                        if stage3_perfect == len(stage2_wrong_cards):
                                            result['practice'].add(2)
                                            result['practice'].add(3)
                                            result['perfect_completion'] = True
                                            app.logger.debug(f"[完了ステージ] 完全完了")
                else:
                    app.logger.debug(f"[完了ステージ] Stage1未完了（チャンクベース）")
        
        # 練習履歴の設定
        for stage in [1, 2, 3]:
            result['practice_history'][stage] = stage in result['practice']
                
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result

# ========== ルート定義エリア ==========
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

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
                for setting in settings:
                    saved_ranges[setting[0]] = setting[1] or ''
                    saved_difficulties[setting[0]] = setting[2] or ''
                
        return render_template('dashboard.html', sources=sources, saved_ranges=saved_ranges, saved_difficulties=saved_difficulties)
    except Exception as e:
        app.logger.error(f"ダッシュボード取得エラー: {e}")
        flash("教材一覧の取得に失敗しました")
        return redirect(url_for('login'))

@app.route('/set_page_range_and_prepare/<source>', methods=['POST'])
@login_required
def set_page_range_and_prepare(source):
    page_range = request.form.get('page_range', '').strip()
    difficulty_list = request.form.getlist('difficulty')
    difficulty = ','.join(difficulty_list) if difficulty_list else ''
    user_id = str(current_user.id)
    
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
    except Exception as e:
        app.logger.error(f"user_settings保存エラー: {e}")
        flash("設定の保存に失敗しました")
    
    return redirect(url_for('prepare', source=source))

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
            conn.close()

            if user and check_password_hash(user[2], password):
                login_user(User(user[0], user[1]))
                return redirect(url_for('dashboard'))
            else:
                flash("ログインに失敗しました。ユーザー名またはパスワードが正しくありません。")
        except Exception as e:
            app.logger.error(f"ログイン時のDBエラー: {e}")
            flash("ログイン中にエラーが発生しました")

    return render_template('login.html')

@app.route('/prepare/<source>', methods=['GET', 'POST'])
@login_required
def prepare(source):
    user_id = str(current_user.id)
    
    try:
        app.logger.debug(f"[PREPARE] 開始: source={source}, user_id={user_id}")
        
        if request.method == 'POST':
            # POST処理は既存のまま
            page_range = request.form.get('page_range', '').strip()
            difficulty_list = request.form.getlist('difficulty')
            difficulty = ','.join(difficulty_list) if difficulty_list else ''
            stage_mode = request.form.get('stage')

            if not stage_mode or '-' not in stage_mode:
                flash("学習ステージを選択してください")
                return redirect(url_for('prepare', source=source))

            stage_str, mode = stage_mode.split('-')
            session['stage'] = int(stage_str)
            session['mode'] = mode
            session['page_range'] = page_range
            session['difficulty'] = difficulty

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
            except Exception as e:
                app.logger.error(f"[PREPARE] user_settings保存エラー: {e}")

            return redirect(url_for('study', source=source))

        # GET処理
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
                        session['page_range'] = saved_page_range
                        session['difficulty'] = saved_difficulty
        except Exception as e:
            app.logger.error(f"[PREPARE] user_settings取得エラー: {e}")

        # 🔥 修正版の完了ステージ取得を使用
        try:
            app.logger.debug(f"[PREPARE] completed_stages取得開始")
            completed_raw = get_completed_stages_chunk_aware(user_id, source, saved_page_range, saved_difficulty)
            app.logger.debug(f"[PREPARE] completed_stages取得成功: {completed_raw}")
            
            completed = {
                "test": set(completed_raw.get("test", [])),
                "practice": set(completed_raw.get("practice", [])),
                "perfect_completion": completed_raw.get("perfect_completion", False),
                "practice_history": completed_raw.get("practice_history", {})
            }
            
        except Exception as e:
            app.logger.error(f"[PREPARE] completed_stages取得エラー: {e}")
            completed = {"test": set(), "practice": set(), "perfect_completion": False, "practice_history": {}}

        return render_template(
            'prepare.html',
            source=source,
            completed=completed,
            saved_page_range=saved_page_range,
            saved_difficulty=saved_difficulty
        )
        
    except Exception as e:
        app.logger.error(f"[PREPARE] 全体エラー: {e}")
        flash("準備画面でエラーが発生しました")
        return redirect(url_for('dashboard'))
      
@app.route('/study/<source>')
@login_required  
def study(source):
    try:
        mode = session.get('mode', 'test')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        stage = session.get('stage', 1)
        user_id = str(current_user.id)

        app.logger.debug(f"[STUDY DEBUG] 開始: stage={stage}, mode={mode}, source={source}, user_id={user_id}")

        if stage == 1:
            app.logger.debug(f"[STUDY DEBUG] Stage 1処理開始")
            
            try:
                # 🔥 修正版v2のチャンク進捗取得を使用
                chunk_progress = get_or_create_chunk_progress_fixed_v2(user_id, source, stage, page_range, difficulty)
                app.logger.debug(f"[STUDY DEBUG] チャンク進捗取得結果: {chunk_progress}")
            except Exception as e:
                app.logger.error(f"[STUDY DEBUG] チャンク進捗取得エラー: {e}")
                flash("チャンク進捗の取得に失敗しました。")
                return redirect(url_for('prepare', source=source))
            
            if not chunk_progress:
                app.logger.warning(f"[STUDY DEBUG] チャンク進捗がNull")
                flash("該当するカードが見つかりませんでした。")
                return redirect(url_for('prepare', source=source))
            
            # 🔥 即時復習が必要かチェック
            needs_practice = chunk_progress.get('needs_immediate_practice', False)
            app.logger.debug(f"[STUDY DEBUG] 即時復習が必要か: {needs_practice}, mode={mode}")
            
            if needs_practice and mode == 'test':
                app.logger.debug(f"[STUDY DEBUG] 🔥 即時復習処理開始")
                newly_completed_chunk = chunk_progress.get('newly_completed_chunk')
                app.logger.debug(f"[STUDY DEBUG] 新しく完了したチャンク: {newly_completed_chunk}")
                
                # 即時復習する×問題があるかチェック
                try:
                    practice_cards = get_chunk_practice_cards(user_id, source, stage, newly_completed_chunk, page_range, difficulty)
                    app.logger.debug(f"[STUDY DEBUG] 即時復習カード数: {len(practice_cards) if practice_cards else 0}")
                    
                    if practice_cards:
                        practice_card_ids = [card['id'] for card in practice_cards]
                        app.logger.debug(f"[STUDY DEBUG] 即時復習カードID: {practice_card_ids}")
                    
                except Exception as e:
                    app.logger.error(f"[STUDY DEBUG] 即時復習カード取得エラー: {e}")
                    practice_cards = []
                
                if practice_cards:
                    # 即時復習に切り替え
                    app.logger.debug(f"[STUDY DEBUG] 🚀 即時復習モードに切り替え")
                    session['mode'] = 'chunk_practice'
                    session['practicing_chunk'] = newly_completed_chunk
                    
                    flash(f"🎉 チャンク{newly_completed_chunk}のテストが完了しました！×の問題を練習しましょう。")
                    return redirect(url_for('study', source=source))
                else:
                    # ×問題がない場合は次のチャンクへ
                    app.logger.debug(f"[STUDY DEBUG] ×問題なし、次のチャンクへ")
                    flash(f"🌟 チャンク{newly_completed_chunk}完了！全問正解です。次のチャンクに進みます。")
            
            # 残りの処理は既存のまま...
            # (省略)
        
        # Stage 2・3の処理も既存のまま...
        # (省略)
        
    except Exception as e:
        app.logger.error(f"[STUDY DEBUG] 全体エラー: {e}")
        flash("学習開始でエラーが発生しました")
        return redirect(url_for('prepare', source=source))
    
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
    
# 🔥 Stage 2・3用の専用関数を追加
def get_stage2_cards(source, page_range, user_id, difficulty):
    """Stage 2: Stage 1の×問題を全て取得"""
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

def get_stage3_cards(source, page_range, user_id, difficulty):
    """Stage 3: Stage 2の×問題を全て取得"""
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

@app.route('/complete_chunk', methods=['POST'])
@login_required
def complete_chunk():
    """チャンク完了処理"""
    source = request.json.get('source')
    stage = request.json.get('stage')
    chunk_number = request.json.get('chunk_number')
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # チャンクを完了としてマーク
                cur.execute('''
                    UPDATE chunk_progress 
                    SET completed = true, completed_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND source = %s AND stage = %s AND chunk_number = %s
                ''', (user_id, source, stage, chunk_number))
                conn.commit()
                
        return jsonify({'status': 'ok'})
    except Exception as e:
        app.logger.error(f"チャンク完了エラー: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = data.get('stage')
    mode = data.get('mode')
    user_id = str(current_user.id)

    # 🔥 セッションからモードを取得（より正確）
    session_mode = session.get('mode', mode)
    
    # チャンク練習モードの場合は専用のモード名で記録
    log_mode = 'chunk_practice' if session_mode == 'chunk_practice' else mode

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO study_log (user_id, card_id, result, stage, mode)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, card_id, result, stage, log_mode))
                conn.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        app.logger.error(f"ログ書き込みエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
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
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset_history/<source>', methods=['POST'])
@login_required
def reset_history(source):
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
                
        flash(f"{source} の学習履歴を削除しました。")
    except Exception as e:
        app.logger.error(f"履歴削除エラー: {e}")
        flash("履歴の削除に失敗しました。")

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
   port = int(os.environ.get('PORT', 10000))
   app.run(host='0.0.0.0', port=port)