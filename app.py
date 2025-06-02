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
    """指定チャンクの練習問題を取得（修正版）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 🔥 修正: まず、このチャンクの全カードを取得
                chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
                
                if not chunk_cards:
                    app.logger.warning(f"[練習カード] チャンク{chunk_number}のカードが取得できません")
                    return []
                
                chunk_card_ids = [card['id'] for card in chunk_cards]
                app.logger.debug(f"[練習カード] チャンク{chunk_number}の全カードID: {chunk_card_ids}")
                
                # 🔥 修正: このチャンクでテスト時に×だった問題を取得
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
                app.logger.debug(f"[練習カード] チャンク{chunk_number}のテスト×問題: {wrong_card_ids}")
                
                if not wrong_card_ids:
                    app.logger.info(f"[練習カード] チャンク{chunk_number}に×問題がありません（全問正解）")
                    return []
                
                # 🔥 修正: 練習で○になった問題を除外
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
                app.logger.debug(f"[練習カード] チャンク{chunk_number}の練習○問題: {practiced_correct_ids}")
                
                # 練習が必要な問題 = テスト×問題 - 練習○問題
                need_practice_ids = [cid for cid in wrong_card_ids if cid not in practiced_correct_ids]
                app.logger.debug(f"[練習カード] チャンク{chunk_number}の練習対象: {need_practice_ids}")
                
                if not need_practice_ids:
                    app.logger.info(f"[練習カード] チャンク{chunk_number}の練習完了")
                    return []
                
                # 🔥 修正: 練習対象のカード詳細を取得
                cur.execute('''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE id = ANY(%s)
                    ORDER BY id
                ''', (need_practice_ids,))
                
                records = cur.fetchall()
                
                practice_cards = [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
                app.logger.info(f"[練習カード] チャンク{chunk_number}の練習カード数: {len(practice_cards)}")
                return practice_cards
                
    except Exception as e:
        app.logger.error(f"チャンク{chunk_number}練習問題取得エラー: {e}")
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
                    
                    # 🔥 ここが重要な修正点: リアルタイムでチャンク完了をチェック
                    newly_completed_chunks = []
                    
                    for chunk_num in range(1, total_chunks + 1):
                        was_completed_before = chunk_num in completed_chunks_before
                        
                        # このチャンクの問題を取得
                        chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        
                        if chunk_cards:
                            chunk_card_ids = [card['id'] for card in chunk_cards]
                            
                            # 🔥 修正: 全問題がテスト完了しているかチェック
                            cur.execute('''
                                SELECT COUNT(DISTINCT card_id)
                                FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = 'test' AND card_id = ANY(%s)
                            ''', (user_id, stage, chunk_card_ids))
                            completed_count = cur.fetchone()[0]
                            
                            # 🔥 修正: 全問題完了 && 処理前未完了 → 新規完了
                            if completed_count == len(chunk_card_ids) and not was_completed_before:
                                cur.execute('''
                                    UPDATE chunk_progress 
                                    SET completed = true, completed_at = CURRENT_TIMESTAMP
                                    WHERE user_id = %s AND source = %s AND stage = %s AND chunk_number = %s AND completed = false
                                ''', (user_id, source, stage, chunk_num))
                                newly_completed_chunks.append(chunk_num)
                                app.logger.info(f"🎉 チャンク{chunk_num}が新規完了!")
                    
                    conn.commit()
                    
                    # 完了済みチャンクを再取得
                    cur.execute('''
                        SELECT chunk_number FROM chunk_progress 
                        WHERE user_id = %s AND source = %s AND stage = %s AND completed = true
                        ORDER BY chunk_number
                    ''', (user_id, source, stage))
                    completed_chunks_after = [row[0] for row in cur.fetchall()]
                    
                    # 🔥 修正: 結果の構築
                    if len(completed_chunks_after) < total_chunks:
                        next_chunk = len(completed_chunks_after) + 1
                        result = {
                            'current_chunk': next_chunk,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after
                        }
                    else:
                        result = {
                            'current_chunk': None,
                            'total_chunks': total_chunks,
                            'completed_chunks': completed_chunks_after,
                            'all_completed': True
                        }
                    
                    # 🔥 修正: 新規完了チャンクがあれば即時練習フラグ
                    if newly_completed_chunks:
                        result['newly_completed_chunk'] = max(newly_completed_chunks)
                        result['needs_immediate_practice'] = True
                    else:
                        result['needs_immediate_practice'] = False
                    
                    return result
                    
                else:
                    # 新規作成の場合（既存のロジックそのまま）
                    cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
                    
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
                        'completed_chunks': [],
                        'needs_immediate_practice': False
                    }
                    
    except Exception as e:
        app.logger.error(f"チャンク進捗取得エラー: {e}")
        return None

# 2. ステージ別カード取得関数
def get_stage_cards_all(source, stage, page_range, user_id, difficulty):
    """ステージ別の全対象カードを取得"""
    if stage == 1:
        # ステージ1: 全問題
        return get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
    elif stage == 2:
        # ステージ2: ステージ1の×問題
        return get_stage2_cards(source, page_range, user_id, difficulty)
    elif stage == 3:
        # ステージ3: ステージ2の×問題
        return get_stage3_cards(source, page_range, user_id, difficulty)
    else:
        # ステージ4以降: 前ステージの×問題
        return get_stage_unknown_cards(source, stage-1, page_range, user_id, difficulty)

def get_stage_cards_by_chunk(source, stage, page_range, user_id, difficulty, chunk_number):
    """ステージ別の指定チャンクカードを取得"""
    # まず全カードを取得
    all_cards = get_stage_cards_all(source, stage, page_range, user_id, difficulty)
    
    if not all_cards:
        return []
    
    # チャンク分割
    subject = all_cards[0]['subject']
    chunk_size = get_chunk_size_by_subject(subject)
    chunks = create_chunks_for_cards(all_cards, subject)
    
    if 1 <= chunk_number <= len(chunks):
        return chunks[chunk_number - 1]
    else:
        return []

# 3. 汎用×問題取得関数
def get_stage_unknown_cards(source, from_stage, page_range, user_id, difficulty):
    """指定ステージの×問題を取得"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # ベースクエリ
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE source = %s
                '''
                params = [source]

                # ページ範囲・難易度フィルタ（既存ロジック）
                # ... (省略)

                # 指定ステージの×問題のみ
                query += '''
                    AND id IN (
                        SELECT card_id FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'test'
                        ) AS ranked
                        WHERE rn = 1 AND result = 'unknown'
                    )
                '''
                params.extend([user_id, from_stage])

                query += ' ORDER BY id'
                cur.execute(query, params)
                records = cur.fetchall()

                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
    except Exception as e:
        app.logger.error(f"Stage{from_stage}×問題取得エラー: {e}")
        return []

# 4. チャンク練習問題取得（汎用版）
def get_chunk_practice_cards_universal(user_id, source, stage, chunk_number, page_range, difficulty):
    """全ステージ対応のチャンク練習問題取得"""
    try:
        # このチャンクの全カードを取得
        chunk_cards = get_stage_cards_by_chunk(source, stage, page_range, user_id, difficulty, chunk_number)
        
        if not chunk_cards:
            return []
        
        chunk_card_ids = [card['id'] for card in chunk_cards]
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # このチャンクでテスト時に×だった問題のうち、練習で○になっていない問題
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
                            WHERE user_id = %s AND stage = %s AND mode = 'chunk_practice'
                            AND card_id = ANY(%s)
                        ) AS practice_ranked
                        WHERE rn = 1 AND result = 'known'
                    )
                    ORDER BY id
                '''
                
                cur.execute(query, (
                    chunk_card_ids,
                    user_id, stage, chunk_card_ids,
                    user_id, stage, chunk_card_ids
                ))
                
                records = cur.fetchall()
                
                return [dict(
                    id=r[0], subject=r[1], grade=r[2], source=r[3],
                    page_number=r[4], problem_number=r[5], topic=r[6],
                    level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
                ) for r in records]
                
    except Exception as e:
        app.logger.error(f"Stage{stage} チャンク{chunk_number} 練習問題取得エラー: {e}")
        return []

# 5. ステージ完了判定（汎用版）
def check_stage_completion(user_id, source, stage, page_range, difficulty):
    """ステージが完全に完了しているかチェック"""
    try:
        chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
        
        if not chunk_progress:
            return False
        
        # 全チャンク完了かつ練習も完了している
        if chunk_progress.get('all_completed'):
            # さらに×問題の練習も完了しているかチェック
            stage_cards = get_stage_cards_all(source, stage, page_range, user_id, difficulty)
            if not stage_cards:
                return True
            
            # この実装では、チャンク即時練習完了=ステージ完了とする
            return True
        
        return False
        
    except Exception as e:
        app.logger.error(f"Stage{stage}完了判定エラー: {e}")
        return False
    
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
                        
                session['page_range'] = page_range
                session['difficulty'] = difficulty
                flash("設定を保存しました。")
                
            except Exception as e:
                app.logger.error(f"設定保存エラー: {e}")
                flash("設定の保存に失敗しました。")

            return redirect(url_for('prepare', source=source))

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
            app.logger.error(f"設定取得エラー: {e}")

        # 🔥 最小限のstages_info
        stages_info = [{
            'stage': 1,
            'stage_name': 'ステージ 1',
            'total_cards': 10,
            'total_chunks': 3,
            'chunks_progress': [
                {
                    'chunk_number': 1,
                    'total_cards': 3,
                    'test_completed': False,
                    'test_correct': 0,
                    'test_wrong': 0,
                    'practice_needed': False,
                    'practice_completed': False,
                    'chunk_completed': False,
                    'can_start_test': True,
                    'can_start_practice': False
                }
            ],
            'stage_completed': False,
            'can_start': True
        }]

        return render_template(
            'prepare_new.html',
            source=source,
            stages_info=stages_info,
            saved_page_range=saved_page_range,
            saved_difficulty=saved_difficulty
        )
        
    except Exception as e:
        app.logger.error(f"準備画面エラー: {e}")
        flash("準備画面でエラーが発生しました")
        return redirect(url_for('dashboard'))

# 🔥 新機能：全ステージの詳細進捗取得
#def get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty):
    """全ステージの詳細進捗情報を取得"""
    stages_info = []
    
    try:
        # ステージ1から順番にチェック
        for stage in range(1, 5):  # ステージ1〜4
            stage_info = get_stage_detailed_progress(user_id, source, stage, page_range, difficulty)
            
            if stage_info:
                stages_info.append(stage_info)
                
                # このステージが未完了なら以降のステージは表示しない
                if not stage_info.get('stage_completed', False):
                    break
            else:
                # カードがない場合は終了
                break
                
        app.logger.debug(f"[詳細進捗] 取得完了: {len(stages_info)}ステージ")
        return stages_info
        
    except Exception as e:
        app.logger.error(f"[詳細進捗] エラー: {e}")
        return []

#def get_stage_detailed_progress(user_id, source, stage, page_range, difficulty):
    """指定ステージの詳細進捗を取得"""
    try:
        app.logger.debug(f"[ステージ進捗] Stage{stage}開始")
        
        # ステージ別の対象カードを取得
        if stage == 1:
            target_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
        else:
            # Stage 2以降は前ステージの×問題
            if stage == 2:
                target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
            elif stage == 3:
                target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
            else:
                target_cards = get_stage_unknown_cards(source, stage-1, page_range, user_id, difficulty)
        
        if not target_cards:
            app.logger.debug(f"[ステージ進捗] Stage{stage}: 対象カードなし")
            return None
        
        # チャンク情報を取得
        subject = target_cards[0]['subject']
        chunk_size = get_chunk_size_by_subject(subject)
        chunks = create_chunks_for_cards(target_cards, subject)
        total_chunks = len(chunks)
        
        app.logger.debug(f"[ステージ進捗] Stage{stage}: {len(target_cards)}問, {total_chunks}チャンク")
        
        # 各チャンクの進捗を取得
        chunks_progress = []
        stage_completed = True
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for chunk_num in range(1, total_chunks + 1):
                    chunk_cards = chunks[chunk_num - 1]
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
                    cur.execute('''
                        SELECT card_id, result FROM (
                            SELECT card_id, result,
                                   ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                            FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'chunk_practice'
                            AND card_id = ANY(%s)
                        ) AS ranked
                        WHERE rn = 1
                    ''', (user_id, stage, chunk_card_ids))
                    practice_results = dict(cur.fetchall())
                    
                    # チャンク状態を判定
                    test_completed = len(test_results) == len(chunk_card_ids)
                    test_wrong_cards = [cid for cid, result in test_results.items() if result == 'unknown']
                    practice_completed = True
                    
                    if test_wrong_cards:
                        # ×問題がある場合、練習で全て○になっているかチェック
                        practice_correct_cards = [cid for cid, result in practice_results.items() if result == 'known']
                        practice_completed = len(set(test_wrong_cards) & set(practice_correct_cards)) == len(test_wrong_cards)
                    
                    chunk_completed = test_completed and practice_completed
                    
                    if not chunk_completed:
                        stage_completed = False
                    
                    chunk_progress = {
                        'chunk_number': chunk_num,
                        'total_cards': len(chunk_card_ids),
                        'test_completed': test_completed,
                        'test_correct': len([r for r in test_results.values() if r == 'known']),
                        'test_wrong': len(test_wrong_cards),
                        'practice_needed': len(test_wrong_cards) > 0,
                        'practice_completed': practice_completed,
                        'chunk_completed': chunk_completed,
                        'can_start_test': chunk_num == 1 or chunks_progress[chunk_num-2]['chunk_completed'],
                        'can_start_practice': test_completed and len(test_wrong_cards) > 0
                    }
                    
                    chunks_progress.append(chunk_progress)
        
        stage_info = {
            'stage': stage,
            'stage_name': f'ステージ {stage}',
            'total_cards': len(target_cards),
            'total_chunks': total_chunks,
            'chunks_progress': chunks_progress,
            'stage_completed': stage_completed,
            'can_start': stage == 1 or (stage > 1)  # Stage 1は常に開始可能、2以降は前ステージ完了で開始可能
        }
        
        app.logger.debug(f"[ステージ進捗] Stage{stage}完了: stage_completed={stage_completed}")
        return stage_info
        
    except Exception as e:
        app.logger.error(f"[ステージ進捗] Stage{stage}エラー: {e}")
        return None

#@app.route('/start_chunk/<source>/<int:stage>/<int:chunk_number>/<mode>')

@login_required
def start_chunk(source, stage, chunk_number, mode):
    """指定チャンクの学習を開始"""
    try:
        user_id = str(current_user.id)
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        app.logger.info(f"[START_CHUNK] Stage{stage} チャンク{chunk_number} {mode}モード開始")
        
        # セッションに学習情報を設定
        session['stage'] = stage
        session['current_source'] = source
        session['page_range'] = page_range
        session['difficulty'] = difficulty
        
        if mode == 'test':
            session['mode'] = 'test'
            session.pop('practicing_chunk', None)
        elif mode == 'practice':
            session['mode'] = 'chunk_practice'
            session['practicing_chunk'] = chunk_number
        
        flash(f"ステージ{stage} チャンク{chunk_number}の{mode}を開始します！")
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"[START_CHUNK] エラー: {e}")
        flash("学習開始に失敗しました")
        return redirect(url_for('prepare', source=source))
    
@app.route('/study/<source>')
@login_required  
def study(source):
    try:
        # 現在の教材名をセッションに保存
        session['current_source'] = source
        
        mode = session.get('mode', 'test')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        stage = session.get('stage', 1)
        user_id = str(current_user.id)

        app.logger.debug(f"[STUDY] 開始: stage={stage}, mode={mode}, source={source}, user_id={user_id}")

        # Stage 1の処理
        if stage == 1:
            app.logger.debug(f"[STUDY] Stage 1処理開始")
            
            try:
                chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
                app.logger.debug(f"[STUDY] チャンク進捗取得結果: {chunk_progress}")
            except Exception as e:
                app.logger.error(f"[STUDY] チャンク進捗取得エラー: {e}")
                flash("チャンク進捗の取得に失敗しました。")
                return redirect(url_for('prepare', source=source))
            
            if not chunk_progress:
                flash("該当するカードが見つかりませんでした。")
                return redirect(url_for('prepare', source=source))
            
            # URLパラメータで即時練習モードを判定
            start_practice = request.args.get('start_practice')
            if start_practice and start_practice.isdigit():
                practicing_chunk = int(start_practice)
                app.logger.info(f"[STUDY] URLパラメータで即時練習開始: チャンク{practicing_chunk}")
                
                # 練習カードを取得
                practice_cards = get_chunk_practice_cards(user_id, source, stage, practicing_chunk, page_range, difficulty)
                
                if practice_cards:
                    session['mode'] = 'chunk_practice'
                    session['practicing_chunk'] = practicing_chunk
                    mode = 'chunk_practice'
                    
                    flash(f"🎉 チャンク{practicing_chunk}のテストが完了しました！×の問題を練習しましょう。")
                else:
                    flash(f"🌟 チャンク{practicing_chunk}完了！全問正解です。次のチャンクに進みます。")
            
            # 全チャンク完了チェック
            if chunk_progress.get('all_completed') and mode != 'chunk_practice':
                app.logger.debug(f"[STUDY] 全チャンク完了")
                flash("🏆 Stage 1の全チャンクが完了しました！")
                return redirect(url_for('prepare', source=source))
            
            # チャンク練習モード
            if mode == 'chunk_practice':
                app.logger.debug(f"[STUDY] チャンク練習モード")
                current_chunk = session.get('practicing_chunk')
                
                try:
                    cards_dict = get_chunk_practice_cards(user_id, source, stage, current_chunk, page_range, difficulty)
                    app.logger.debug(f"[STUDY] 練習カード数: {len(cards_dict) if cards_dict else 0}")
                except Exception as e:
                    app.logger.error(f"[STUDY] 練習カード取得エラー: {e}")
                    cards_dict = []
                
                if not cards_dict:
                    # 練習完了 → テストモードに戻る
                    flash(f"✅ チャンク{current_chunk}の復習完了！次のチャンクに進みます。")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('study', source=source))
                
                total_chunks = chunk_progress['total_chunks']
                current_chunk = session.get('practicing_chunk')
                
            else:
                # テストモード
                app.logger.debug(f"[STUDY] Stage 1テストモード")
                current_chunk = chunk_progress['current_chunk']
                total_chunks = chunk_progress['total_chunks']
                
                if current_chunk is None:
                    app.logger.warning(f"[STUDY] current_chunk=None, 全チャンク完了判定")
                    flash("🏆 Stage 1の全チャンクが完了しました！")
                    return redirect(url_for('prepare', source=source))
                
                try:
                    cards_dict = get_study_cards(source, stage, mode, page_range, user_id, difficulty, current_chunk)
                    app.logger.debug(f"[STUDY] Stage 1テストカード数: {len(cards_dict) if cards_dict else 0}")
                except Exception as e:
                    app.logger.error(f"[STUDY] Stage 1テストカード取得エラー: {e}")
                    cards_dict = []
        
        # Stage 2・3の処理
        elif stage in [2, 3]:
            app.logger.debug(f"[STUDY] Stage {stage}処理開始")
            
            try:
                chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
                app.logger.debug(f"[STUDY] Stage {stage}チャンク進捗: {chunk_progress}")
            except Exception as e:
                app.logger.error(f"[STUDY] Stage {stage}チャンク進捗エラー: {e}")
                chunk_progress = None
            
            if not chunk_progress:
                flash(f"Stage {stage}で学習する×問題がありません。")
                return redirect(url_for('prepare', source=source))
            
            # 全チャンク完了チェック
            if chunk_progress.get('all_completed'):
                app.logger.debug(f"[STUDY] Stage {stage} 全チャンク完了")
                flash(f"🏆 Stage {stage}の全チャンクが完了しました！")
                return redirect(url_for('prepare', source=source))
            
            # 即時復習チェック
            needs_practice = chunk_progress.get('needs_immediate_practice', False)
            if needs_practice and mode == 'test':
                newly_completed_chunk = chunk_progress.get('newly_completed_chunk')
                practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, newly_completed_chunk, page_range, difficulty)
                
                if practice_cards:
                    session['mode'] = 'chunk_practice'
                    session['practicing_chunk'] = newly_completed_chunk
                    flash(f"🎉 Stage {stage} チャンク{newly_completed_chunk}完了！×の問題を練習しましょう。")
                    return redirect(url_for('study', source=source))
            
            # チャンク練習モード
            if mode == 'chunk_practice':
                current_chunk = session.get('practicing_chunk')
                cards_dict = get_chunk_practice_cards_universal(user_id, source, stage, current_chunk, page_range, difficulty)
                
                if not cards_dict:
                    flash(f"✅ Stage {stage} チャンク{current_chunk}の復習完了！")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('study', source=source))
                
                total_chunks = chunk_progress['total_chunks']
                current_chunk = session.get('practicing_chunk')
            else:
                current_chunk = chunk_progress['current_chunk']
                total_chunks = chunk_progress['total_chunks']
                
                if current_chunk is None:
                    app.logger.warning(f"[STUDY] Stage {stage}: current_chunk=None, 完了判定へ")
                    flash(f"🏆 Stage {stage}の全チャンクが完了しました！")
                    return redirect(url_for('prepare', source=source))
                
                cards_dict = get_stage_cards_by_chunk(source, stage, page_range, user_id, difficulty, current_chunk)
        
        else:
            app.logger.warning(f"[STUDY] 不正なステージ番号: {stage}")
            cards_dict = []
            current_chunk = None
            total_chunks = 1

        # 問題がない場合の処理
        if not cards_dict:
            app.logger.warning(f"[STUDY] カードが取得できない: stage={stage}, current_chunk={current_chunk}")
            if stage in [2, 3]:
                flash(f"Stage {stage}で学習する×問題がありません。前のStageで×問題を作ってください。")
            else:
                flash("該当するカードが見つかりませんでした。")
            return redirect(url_for('prepare', source=source))

        # テンプレート表示
        app.logger.debug(f"[STUDY] テンプレート表示: stage={stage}, 問題数={len(cards_dict)}, current_chunk={current_chunk}")

        return render_template('index.html',
                             cards=cards_dict, 
                             mode=mode,
                             current_chunk=current_chunk,
                             total_chunks=total_chunks,
                             stage=stage,
                             source=source)

    except Exception as e:
        app.logger.error(f"[STUDY] 全体エラー: {e}")
        app.logger.error(f"[STUDY] エラートレースバック: ", exc_info=True)
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

# ========== Stage 2・3用の関数（再掲） ==========
# 既存の関数群の後に追加

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

    # セッションからモードを取得（より正確）
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
        
        # 基本レスポンス
        response_data = {'status': 'ok'}
        
        # Stage 1 テストモードの場合、チャンク完了をチェック
        if stage == 1 and session_mode == 'test':
            app.logger.debug(f"[LOG_RESULT] Stage1テスト回答後のチャンク完了チェック")
            
            # セッション情報を取得
            source = session.get('current_source')
            page_range = session.get('page_range', '').strip()
            difficulty = session.get('difficulty', '').strip()
            
            if source:
                try:
                    # チャンク進捗をリアルタイムでチェック
                    chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
                    
                    if chunk_progress and chunk_progress.get('needs_immediate_practice'):
                        newly_completed_chunk = chunk_progress.get('newly_completed_chunk')
                        app.logger.info(f"[LOG_RESULT] 🎉 チャンク{newly_completed_chunk}完了！即時練習が必要")
                        
                        # 練習カードがあるかチェック
                        practice_cards = get_chunk_practice_cards(user_id, source, stage, newly_completed_chunk, page_range, difficulty)
                        
                        if practice_cards:
                            # フロントエンドに即時練習開始を通知
                            response_data.update({
                                'needs_immediate_practice': True,
                                'completed_chunk': newly_completed_chunk,
                                'practice_cards_count': len(practice_cards),
                                'message': f"🎉 チャンク{newly_completed_chunk}完了！×の問題を練習しましょう。"
                            })
                            app.logger.debug(f"[LOG_RESULT] 練習カード{len(practice_cards)}問を検出")
                        else:
                            # ×問題がない場合
                            response_data.update({
                                'chunk_perfect': True,
                                'completed_chunk': newly_completed_chunk,
                                'message': f"🌟 チャンク{newly_completed_chunk}完了！全問正解です。"
                            })
                            app.logger.debug(f"[LOG_RESULT] チャンク{newly_completed_chunk}は全問正解")
                            
                except Exception as e:
                    app.logger.error(f"[LOG_RESULT] チャンク完了チェックエラー: {e}")
        
        # チャンク練習モードの完了チェック
        elif stage == 1 and session_mode == 'chunk_practice':
            app.logger.debug(f"[LOG_RESULT] チャンク練習回答後の完了チェック")
            
            source = session.get('current_source')
            page_range = session.get('page_range', '').strip()
            difficulty = session.get('difficulty', '').strip()
            practicing_chunk = session.get('practicing_chunk')
            
            if source and practicing_chunk:
                try:
                    # 練習カードが残っているかチェック
                    remaining_practice_cards = get_chunk_practice_cards(user_id, source, stage, practicing_chunk, page_range, difficulty)
                    
                    if not remaining_practice_cards:
                        # 練習完了
                        response_data.update({
                            'practice_complete': True,
                            'completed_chunk': practicing_chunk,
                            'message': f"✅ チャンク{practicing_chunk}の復習完了！"
                        })
                        app.logger.info(f"[LOG_RESULT] チャンク{practicing_chunk}の練習完了")
                    else:
                        app.logger.debug(f"[LOG_RESULT] チャンク{practicing_chunk}の練習継続（残り{len(remaining_practice_cards)}問）")
                        
                except Exception as e:
                    app.logger.error(f"[LOG_RESULT] 練習完了チェックエラー: {e}")
        
        app.logger.debug(f"[LOG_RESULT] レスポンス: {response_data}")
        return jsonify(response_data)
        
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

# ========== 既存のコード（920行目付近） ==========

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

# 🔥 ここに新しいルートを追加 🔥
# ========== チャンク練習関連ルート ==========

@app.route('/start_chunk_practice/<source>/<int:chunk_number>')
@login_required
def start_chunk_practice(source, chunk_number):
    """チャンク練習を開始"""
    try:
        user_id = str(current_user.id)
        stage = session.get('stage', 1)
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        
        app.logger.info(f"[START_PRACTICE] チャンク{chunk_number}の練習開始: user_id={user_id}, stage={stage}")
        
        # 練習カードがあるかチェック
        if stage == 1:
            practice_cards = get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty)
        else:
            practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, chunk_number, page_range, difficulty)
        
        if practice_cards:
            # 練習モードに切り替え
            session['mode'] = 'chunk_practice'
            session['practicing_chunk'] = chunk_number
            session['current_source'] = source
            
            app.logger.info(f"[START_PRACTICE] 練習カード{len(practice_cards)}問を開始")
            flash(f"🎉 チャンク{chunk_number}の復習を開始します！（{len(practice_cards)}問）")
        else:
            app.logger.info(f"[START_PRACTICE] チャンク{chunk_number}は練習対象なし")
            flash(f"🌟 チャンク{chunk_number}は全問正解でした！")
        
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"[START_PRACTICE] 練習開始エラー: {e}")
        flash("練習の開始に失敗しました")
        return redirect(url_for('study', source=source))

@app.route('/skip_chunk_practice/<source>')
@login_required
def skip_chunk_practice(source):
    """チャンク練習をスキップして次のチャンクへ"""
    try:
        app.logger.info(f"[SKIP_PRACTICE] 練習をスキップ")
        
        # 練習モードをリセット
        session['mode'] = 'test'
        session.pop('practicing_chunk', None)
        session['current_source'] = source
        
        flash("練習をスキップしました。次のチャンクに進みます。")
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"[SKIP_PRACTICE] スキップエラー: {e}")
        flash("スキップに失敗しました")
        return redirect(url_for('study', source=source))

@app.route('/complete_chunk_practice/<source>')
@login_required
def complete_chunk_practice(source):
    """チャンク練習を完了してテストモードに戻る"""
    try:
        practicing_chunk = session.get('practicing_chunk')
        app.logger.info(f"[COMPLETE_PRACTICE] チャンク{practicing_chunk}の練習完了")
        
        # テストモードに戻る
        session['mode'] = 'test'
        session.pop('practicing_chunk', None)
        session['current_source'] = source
        
        if practicing_chunk:
            flash(f"✅ チャンク{practicing_chunk}の復習が完了しました！次のチャンクに進みます。")
        else:
            flash("復習が完了しました！")
            
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"[COMPLETE_PRACTICE] 完了処理エラー: {e}")
        flash("完了処理に失敗しました")
        return redirect(url_for('study', source=source))

# 🔥 ここにデバッグ用ルートを追加 🔥
# ========== デバッグ・開発用ルート ==========

@app.route('/debug/chunk_status/<source>')
@login_required
def debug_chunk_status(source):
    """チャンク状況の詳細デバッグ"""
    user_id = str(current_user.id)
    page_range = session.get('page_range', '').strip()
    difficulty = session.get('difficulty', '').strip()
    stage = session.get('stage', 1)
    
    try:
        import traceback
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # チャンク進捗状況
                cur.execute('''
                    SELECT chunk_number, total_chunks, completed, completed_at 
                    FROM chunk_progress 
                    WHERE user_id = %s AND source = %s AND stage = %s
                    ORDER BY chunk_number
                ''', (user_id, source, stage))
                chunk_progress = cur.fetchall()
                
                # セッション情報
                session_info = {
                    'mode': session.get('mode'),
                    'practicing_chunk': session.get('practicing_chunk'),
                    'current_source': session.get('current_source'),
                    'stage': session.get('stage'),
                    'page_range': session.get('page_range'),
                    'difficulty': session.get('difficulty')
                }
                
                # 各チャンクのカード状況
                debug_info = {
                    'user_id': user_id,
                    'source': source,
                    'stage': stage,
                    'page_range': page_range,
                    'difficulty': difficulty,
                    'session_info': session_info,
                    'chunk_progress': chunk_progress,
                    'chunks_detail': []
                }
                
                # 最大5チャンクまでチェック
                for chunk_num in range(1, 6):
                    try:
                        if stage == 1:
                            chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_num)
                        else:
                            chunk_cards = get_stage_cards_by_chunk(source, stage, page_range, user_id, difficulty, chunk_num)
                        
                        if not chunk_cards:
                            continue
                        
                        chunk_card_ids = [card['id'] for card in chunk_cards]
                        
                        # テスト状況
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
                        
                        # 練習状況
                        cur.execute('''
                            SELECT card_id, result FROM (
                                SELECT card_id, result,
                                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY id DESC) AS rn
                                FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = 'chunk_practice'
                                AND card_id = ANY(%s)
                            ) AS ranked
                            WHERE rn = 1
                        ''', (user_id, stage, chunk_card_ids))
                        practice_results = dict(cur.fetchall())
                        
                        # 練習対象カード（現在の状況）
                        if stage == 1:
                            current_practice_cards = get_chunk_practice_cards(user_id, source, stage, chunk_num, page_range, difficulty)
                        else:
                            current_practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, chunk_num, page_range, difficulty)
                        
                        chunk_detail = {
                            'chunk_number': chunk_num,
                            'total_cards': len(chunk_card_ids),
                            'card_ids': chunk_card_ids,
                            'test_results': test_results,
                            'practice_results': practice_results,
                            'tested_count': len(test_results),
                            'correct_count': len([r for r in test_results.values() if r == 'known']),
                            'wrong_count': len([r for r in test_results.values() if r == 'unknown']),
                            'practice_correct_count': len([r for r in practice_results.values() if r == 'known']),
                            'practice_wrong_count': len([r for r in practice_results.values() if r == 'unknown']),
                            'current_practice_cards_count': len(current_practice_cards) if current_practice_cards else 0,
                            'current_practice_card_ids': [c['id'] for c in current_practice_cards] if current_practice_cards else [],
                            'is_test_complete': len(test_results) == len(chunk_card_ids),
                            'is_practice_complete': len(current_practice_cards) == 0 if current_practice_cards is not None else None
                        }
                        
                        debug_info['chunks_detail'].append(chunk_detail)
                        
                    except Exception as e:
                        debug_info['chunks_detail'].append({
                            'chunk_number': chunk_num,
                            'error': str(e)
                        })
                
                # 現在のチャンク進捗を取得
                try:
                    if stage == 1:
                        current_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
                    else:
                        current_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
                    debug_info['current_progress'] = current_progress
                except Exception as e:
                    debug_info['current_progress'] = {'error': str(e)}
                
                return f"""
                <html>
                <head>
                    <title>チャンクデバッグ - {source}</title>
                    <style>
                        body {{ font-family: monospace; margin: 20px; }}
                        .header {{ background-color: #f8f9fa; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                        .navigation {{ margin-bottom: 20px; }}
                        .navigation a {{ margin-right: 15px; padding: 8px 12px; background-color: #007bff; color: white; text-decoration: none; border-radius: 3px; }}
                        .navigation a:hover {{ background-color: #0056b3; }}
                        .chunk {{ border: 1px solid #ccc; margin: 10px 0; padding: 10px; border-radius: 5px; }}
                        .complete {{ background-color: #d4edda; }}
                        .incomplete {{ background-color: #f8d7da; }}
                        .in-progress {{ background-color: #fff3cd; }}
                        pre {{ white-space: pre-wrap; word-wrap: break-word; background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                        .summary {{ background-color: #e9ecef; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>🔍 チャンクデバッグ情報</h1>
                        <p><strong>教材:</strong> {source} | <strong>ステージ:</strong> {stage} | <strong>ユーザー:</strong> {user_id}</p>
                    </div>
                    
                    <div class="navigation">
                        <a href="/study/{source}">📚 学習画面に戻る</a>
                        <a href="/prepare/{source}">⚙️ 準備画面に戻る</a>
                        <a href="/api/chunk_status/{source}">📄 JSON形式</a>
                        <a href="/dashboard">🏠 ダッシュボード</a>
                    </div>
                    
                    <div class="summary">
                        <h3>📊 概要</h3>
                        <p><strong>現在のモード:</strong> {session_info.get('mode', 'なし')}</p>
                        <p><strong>練習中チャンク:</strong> {session_info.get('practicing_chunk', 'なし')}</p>
                        <p><strong>チャンク進捗:</strong> {len([c for c in chunk_progress if c[2]])} / {len(chunk_progress)} 完了</p>
                    </div>
                    
                    <h3>🗂️ 詳細データ</h3>
                    <pre>{json.dumps(debug_info, indent=2, ensure_ascii=False, default=str)}</pre>
                </body>
                </html>
                """
        
    except Exception as e:
        return f"<pre>❌ デバッグエラー: {str(e)}\n\n{traceback.format_exc()}</pre>"

@app.route('/api/chunk_status/<source>')
@login_required
def api_chunk_status(source):
    """チャンク状況をJSON形式で返す（API用）"""
    user_id = str(current_user.id)
    page_range = session.get('page_range', '').strip()
    difficulty = session.get('difficulty', '').strip()
    stage = session.get('stage', 1)
    
    try:
        if stage == 1:
            chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
        else:
            chunk_progress = get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty)
        
        if not chunk_progress:
            return jsonify({'status': 'error', 'message': 'チャンク進捗が取得できません'})
        
        # 練習が必要なチャンクをチェック
        needs_practice_chunks = []
        if chunk_progress.get('needs_immediate_practice'):
            chunk_num = chunk_progress.get('newly_completed_chunk')
            if chunk_num:
                if stage == 1:
                    practice_cards = get_chunk_practice_cards(user_id, source, stage, chunk_num, page_range, difficulty)
                else:
                    practice_cards = get_chunk_practice_cards_universal(user_id, source, stage, chunk_num, page_range, difficulty)
                
                if practice_cards:
                    needs_practice_chunks.append({
                        'chunk_number': chunk_num,
                        'practice_cards_count': len(practice_cards)
                    })
        
        return jsonify({
            'status': 'ok',
            'current_chunk': chunk_progress.get('current_chunk'),
            'total_chunks': chunk_progress.get('total_chunks'),
            'completed_chunks': chunk_progress.get('completed_chunks', []),
            'all_completed': chunk_progress.get('all_completed', False),
            'needs_immediate_practice': chunk_progress.get('needs_immediate_practice', False),
            'needs_practice_chunks': needs_practice_chunks,
            'session_mode': session.get('mode'),
            'practicing_chunk': session.get('practicing_chunk')
        })
        
    except Exception as e:
        app.logger.error(f"チャンク状況API エラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
   port = int(os.environ.get('PORT', 10000))
   app.run(host='0.0.0.0', port=port)