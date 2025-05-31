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

                # モード・ステージ別の条件
                if mode == 'test':
                    if stage == 1:
                        pass
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
                
                elif mode == 'practice':
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
                cur.execute(query, params)
                records = cur.fetchall()

        cards_dict = [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]

        # チャンク分割処理
        if chunk_number and cards_dict:
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

    if request.method == 'POST':
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
            app.logger.error(f"user_settings保存エラー: {e}")

        return redirect(url_for('study', source=source))

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
        app.logger.error(f"user_settings取得エラー: {e}")

    try:
        completed_raw = get_completed_stages(user_id, source, saved_page_range, saved_difficulty)
        completed = {
            "test": set(completed_raw.get("test", [])),
            "practice": set(completed_raw.get("practice", [])),
            "perfect_completion": completed_raw.get("perfect_completion", False),
            "practice_history": completed_raw.get("practice_history", {})
        }
        
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")
        completed = {"test": set(), "practice": set(), "perfect_completion": False, "practice_history": {}}

    return render_template(
        'prepare.html',
        source=source,
        completed=completed,
        saved_page_range=saved_page_range,
        saved_difficulty=saved_difficulty
    )

@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')
    page_range = session.get('page_range', '').strip()
    difficulty = session.get('difficulty', '').strip()
    stage = session.get('stage', 1)
    user_id = str(current_user.id)

    # チャンク進捗を取得
    chunk_progress = get_or_create_chunk_progress(user_id, source, stage, page_range, difficulty)
    
    if not chunk_progress:
        flash("該当するカードが見つかりませんでした。")
        return redirect(url_for('prepare', source=source))
    
    # 🔥 即時復習が必要かチェック（新機能）
    if chunk_progress.get('needs_immediate_practice') and mode == 'test':
        newly_completed_chunk = chunk_progress['newly_completed_chunk']
        
        # 即時復習する×問題があるかチェック
        practice_cards = get_chunk_practice_cards(user_id, source, stage, newly_completed_chunk, page_range, difficulty)
        
        if practice_cards:
            # 即時復習に切り替え
            session['mode'] = 'chunk_practice'
            session['practicing_chunk'] = newly_completed_chunk
            
            flash(f"🎉 チャンク{newly_completed_chunk}のテストが完了しました！×の問題を練習しましょう。")
            return redirect(url_for('study', source=source))
        else:
            # ×問題がない場合は次のチャンクへ
            flash(f"🌟 チャンク{newly_completed_chunk}完了！全問正解です。次のチャンクに進みます。")
    
    # 全チャンク完了チェック
    if chunk_progress.get('all_completed') and mode != 'chunk_practice':
        flash("🏆 このステージの全チャンクが完了しました！")
        return redirect(url_for('prepare', source=source))
    
    # 🔥 チャンク練習モードの処理（新機能）
    if mode == 'chunk_practice':
        current_chunk = session.get('practicing_chunk')
        
        # 練習問題を取得
        cards_dict = get_chunk_practice_cards(user_id, source, stage, current_chunk, page_range, difficulty)
        
        if not cards_dict:
            # 練習完了 → テストモードに戻る
            flash(f"✅ チャンク{current_chunk}の復習完了！次のチャンクに進みます。")
            session['mode'] = 'test'
            session.pop('practicing_chunk', None)
            return redirect(url_for('study', source=source))
        
        total_chunks = chunk_progress['total_chunks']
        
    else:
        current_chunk = chunk_progress['current_chunk']
        total_chunks = chunk_progress['total_chunks']
        
        # 通常のテスト問題を取得
        cards_dict = get_study_cards(source, stage, mode, page_range, user_id, difficulty, current_chunk)

    if not cards_dict:
        flash("該当するカードが見つかりませんでした。")
        return redirect(url_for('prepare', source=source))

    # チャンク情報をテンプレートに渡す
    return render_template('index.html', 
                         cards=cards_dict, 
                         mode=mode,
                         current_chunk=current_chunk,
                         total_chunks=total_chunks)

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