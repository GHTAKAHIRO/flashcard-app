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

# ========== 1. 基本ユーティリティ関数群 ==========
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

# ========== 2. User関連（Flask-Login用） ==========
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

# ========== 3. カード取得関数群 ==========
def get_study_cards(source, stage, mode, page_range, user_id, difficulty='', chunk_number=None):
    """統合復習対応版のget_study_cards"""
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

# ========== 4. チャンク進捗管理関数群 ==========
def get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty):
    """Stage 1用のチャンク進捗を取得または作成"""
    try:
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
                        'completed_chunks': []
                    }
                    
    except Exception as e:
        app.logger.error(f"チャンク進捗取得エラー: {e}")
        return None

def get_or_create_chunk_progress_universal(user_id, source, stage, page_range, difficulty):
    """Stage 2・3用のチャンク進捗管理（統合復習対応）"""
    try:
        app.logger.debug(f"[Universal進捗] Stage{stage}開始: user_id={user_id}")
        
        # Stage 2・3は統合復習なので1チャンクとして扱う
        if stage == 2:
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            return get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
        
        if not target_cards:
            app.logger.debug(f"[Universal進捗] Stage{stage}: 対象カードなし")
            return None
        
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
                    ''', (user_id, stage, chunk_number))
                    conn.commit()
                
                result = {
                    'current_chunk': None if all_completed else chunk_number,
                    'total_chunks': total_chunks,
                    'completed_chunks': [chunk_number] if all_completed else [],
                    'all_completed': all_completed,
                    'needs_immediate_practice': False
                }
                
                return result
                
    except Exception as e:
        app.logger.error(f"[Universal進捗] Stage{stage}エラー: {e}")
        return None

# ========== 5. 練習問題取得関数群 ==========
def get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty):
    """Stage 1用の指定チャンクの練習問題を取得"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                chunk_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty, chunk_number)
                
                if not chunk_cards:
                    return []
                
                chunk_card_ids = [card['id'] for card in chunk_cards]
                
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
    """Stage 2・3対応のチャンク練習問題取得"""
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

# ========== 6. 新しい学習設定画面用関数群 ==========
def get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty):
    """全ステージの詳細進捗情報を取得"""
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

def get_stage_detailed_progress(user_id, source, stage, page_range, difficulty):
    """指定ステージの詳細進捗を取得"""
    try:
        # ステージ別の対象カードを取得
        if stage == 1:
            target_cards = get_study_cards(source, stage, 'test', page_range, user_id, difficulty)
        elif stage == 2:
            target_cards = get_stage2_cards(source, page_range, user_id, difficulty)
        elif stage == 3:
            target_cards = get_stage3_cards(source, page_range, user_id, difficulty)
        else:
            target_cards = []
        
        if not target_cards:
            return None
        
        # チャンク情報を取得
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
        
        stage_info = {
            'stage': stage,
            'stage_name': f'ステージ {stage}',
            'total_cards': len(target_cards),
            'total_chunks': total_chunks,
            'chunks_progress': chunks_progress,
            'stage_completed': stage_completed,
            'can_start': True
        }
        
        return stage_info
        
    except Exception as e:
        app.logger.error(f"ステージ進捗エラー: {e}")
        return None

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

# ========== 7. その他のサポート関数群 ==========
def get_completed_stages_chunk_aware(user_id, source, page_range, difficulty=''):
    """チャンク完了を考慮した完了ステージ取得"""
    result = {'test': set(), 'practice': set(), 'perfect_completion': False, 'practice_history': {}}
    user_id = str(user_id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # ステージ1の完了判定（チャンクベース）
                chunk_progress = get_or_create_chunk_progress(user_id, source, 1, page_range, difficulty)
                
                if chunk_progress and chunk_progress.get('all_completed'):
                    result['test'].add(1)
                    result['practice'].add(1)
                    
                    # 以降のステージ判定...
                    # （簡略化のため省略）
        
        # 練習履歴の設定
        for stage in [1, 2, 3]:
            result['practice_history'][stage] = stage in result['practice']
                
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result

# ========== 8. ルート定義エリア ==========
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
            conn.close()

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
        app.logger.error(f"ダッシュボードエラー: {e}")
        flash("教材一覧の取得に失敗しました")
        return redirect(url_for('login'))

@app.route('/set_page_range_and_prepare/<source>', methods=['POST'])
@login_required
def set_page_range_and_prepare(source):
    """ダッシュボードからの設定保存＆準備画面遷移"""
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

@app.route('/prepare/<source>', methods=['GET', 'POST'])
@login_required
def prepare(source):
    user_id = str(current_user.id)
    
    try:
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

        # 詳細進捗情報を取得
        stages_info = get_detailed_progress_for_all_stages(user_id, source, saved_page_range, saved_difficulty)
        
        if not stages_info:
            stages_info = create_fallback_stage_info(source, saved_page_range, saved_difficulty, user_id)

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

@app.route('/start_chunk/<source>/<int:stage>/<int:chunk_number>/<mode>')
@login_required
def start_chunk(source, stage, chunk_number, mode):
    """指定チャンクの学習を開始"""
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
            if stage == 1:
                session['mode'] = 'chunk_practice'
                session['practicing_chunk'] = chunk_number
            else:
                session['mode'] = 'practice'
        
        flash(f"ステージ{stage} チャンク{chunk_number}の{mode}を開始します！")
        return redirect(url_for('study', source=source))
        
    except Exception as e:
        app.logger.error(f"学習開始エラー: {e}")
        flash("学習開始に失敗しました")
        return redirect(url_for('prepare', source=source))

@app.route('/study/<source>')
@login_required  
def study(source):
    try:
        session['current_source'] = source
        
        mode = session.get('mode', 'test')
        page_range = session.get('page_range', '').strip()
        difficulty = session.get('difficulty', '').strip()
        stage = session.get('stage', 1)
        user_id = str(current_user.id)

        # Stage別処理
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
            
            if chunk_progress.get('all_completed') and mode != 'chunk_practice':
                flash("🏆 Stage 1の全チャンクが完了しました！")
                return redirect(url_for('prepare', source=source))
            
            if mode == 'chunk_practice':
                current_chunk = session.get('practicing_chunk')
                cards_dict = get_chunk_practice_cards(user_id, source, stage, current_chunk, page_range, difficulty)
                
                if not cards_dict:
                    flash(f"✅ チャンク{current_chunk}の復習完了！")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('study', source=source))
                
                total_chunks = chunk_progress['total_chunks']
            else:
                current_chunk = chunk_progress['current_chunk']
                total_chunks = chunk_progress['total_chunks']
                
                if current_chunk is None:
                    flash("🏆 Stage 1の全チャンクが完了しました！")
                    return redirect(url_for('prepare', source=source))
                
                cards_dict = get_study_cards(source, stage, mode, page_range, user_id, difficulty, current_chunk)
        
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
            
            if mode == 'chunk_practice':
                current_chunk = session.get('practicing_chunk')
                cards_dict = get_chunk_practice_cards_universal(user_id, source, stage, current_chunk, page_range, difficulty)
                
                if not cards_dict:
                    flash(f"✅ Stage {stage} チャンク{current_chunk}の復習完了！")
                    session['mode'] = 'test'
                    session.pop('practicing_chunk', None)
                    return redirect(url_for('study', source=source))
                
                total_chunks = chunk_progress['total_chunks']
            else:
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

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = data.get('stage')
    mode = data.get('mode')
    user_id = str(current_user.id)

    session_mode = session.get('mode', mode)
    log_mode = 'chunk_practice' if session_mode == 'chunk_practice' else mode

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO study_log (user_id, card_id, result, stage, mode)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, card_id, result, stage, log_mode))
                conn.commit()
        
        response_data = {'status': 'ok'}
        
        # Stage 1 テストモード時のチャンク完了チェック
        if stage == 1 and session_mode == 'test':
            source = session.get('current_source')
            page_range = session.get('page_range', '').strip()
            difficulty = session.get('difficulty', '').strip()
            
            if source:
                try:
                    chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
                    
                    if chunk_progress and chunk_progress.get('needs_immediate_practice'):
                        newly_completed_chunk = chunk_progress.get('newly_completed_chunk')
                        practice_cards = get_chunk_practice_cards(user_id, source, stage, newly_completed_chunk, page_range, difficulty)
                        
                        if practice_cards:
                            response_data.update({
                                'needs_immediate_practice': True,
                                'completed_chunk': newly_completed_chunk,
                                'practice_cards_count': len(practice_cards),
                                'message': f"🎉 チャンク{newly_completed_chunk}完了！×の問題を練習しましょう。"
                            })
                        else:
                            response_data.update({
                                'chunk_perfect': True,
                                'completed_chunk': newly_completed_chunk,
                                'message': f"🌟 チャンク{newly_completed_chunk}完了！全問正解です。"
                            })
                            
                except Exception as e:
                    app.logger.error(f"チャンク完了チェックエラー: {e}")
        
        # チャンク練習モードの完了チェック
        elif stage == 1 and session_mode == 'chunk_practice':
            source = session.get('current_source')
            page_range = session.get('page_range', '').strip()
            difficulty = session.get('difficulty', '').strip()
            practicing_chunk = session.get('practicing_chunk')
            
            if source and practicing_chunk:
                try:
                    remaining_practice_cards = get_chunk_practice_cards(user_id, source, stage, practicing_chunk, page_range, difficulty)
                    
                    if not remaining_practice_cards:
                        response_data.update({
                            'practice_complete': True,
                            'completed_chunk': practicing_chunk,
                            'message': f"✅ チャンク{practicing_chunk}の復習完了！"
                        })
                        
                except Exception as e:
                    app.logger.error(f"練習完了チェックエラー: {e}")
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"ログ書き込みエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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