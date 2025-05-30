from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

import os
import logging
import psycopg2
from dotenv import load_dotenv

# .envファイルの読み込み
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

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# ユーザークラス
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# ログインマネージャのコールバック
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return User(*user)
    return None

def parse_page_range(page_range_str):
    pages = set()
    for part in page_range_str.split(','):
        if '-' in part:
            start, end = part.split('-')
            pages.update(str(i) for i in range(int(start), int(end) + 1))
        else:
            pages.add(part.strip())
    return list(pages)

def get_study_cards(source, stage, mode, page_range, user_id):
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

                # モード・ステージ別の条件
                if mode == 'test':
                    if stage == 1:
                        # Stage 1 テスト: 全問題対象（ページ範囲内）
                        pass  # 既にページ範囲で絞り込み済み
                    elif stage == 2:
                        # Stage 2 テスト: Stage 1 テストで×だった問題のみ
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
                        # Stage 3 テスト: Stage 2 テストで×だった問題のみ
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
                    # 練習モード: 段階的絞り込み方式
                    if stage == 1:
                        # Stage 1 練習: Stage 1 テストで×だった問題から、まだ○になっていない問題
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
                        # Stage 2 練習: Stage 2 テストで×だった問題から、まだ○になっていない問題
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
                        # Stage 3 練習: Stage 3 テストで×だった問題から、まだ○になっていない問題
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

        return cards_dict
    except Exception as e:
        app.logger.error(f"教材取得エラー: {e}")
        return None

def get_completed_stages(user_id, source, page_range):
    result = {'test': set(), 'practice': set(), 'perfect_completion': False}
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
                # 対象となる全カードIDを取得
                if page_numbers:
                    cur.execute('''
                        SELECT id FROM image
                        WHERE source = %s AND page_number::text = ANY(%s)
                    ''', (source, page_numbers))
                else:
                    cur.execute('SELECT id FROM image WHERE source = %s', (source,))
                all_card_ids = [row[0] for row in cur.fetchall()]

                for stage in [1, 2, 3]:
                    # 各ステージのテスト対象カードを決定
                    if stage == 1:
                        target_card_ids = all_card_ids
                    elif stage == 2:
                        # Stage 1 テストが完了している場合のみチェック
                        if 1 not in result['test']:
                            continue  # Stage 1 テスト未完了なので Stage 2 はスキップ
                        
                        # Stage 1 テストで×だった問題が対象
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
                        # Stage 2 テストが完了している場合のみチェック
                        if 2 not in result['test']:
                            continue  # Stage 2 テスト未完了なので Stage 3 はスキップ
                        
                        # Stage 2 テストで×だった問題が対象
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

                    # テストが完了しているかチェック
                    if target_card_ids:
                        cur.execute('''
                            SELECT COUNT(DISTINCT card_id)
                            FROM study_log
                            WHERE user_id = %s AND mode = 'test' AND stage = %s AND card_id = ANY(%s)
                        ''', (user_id, stage, list(target_card_ids)))
                        tested_count = cur.fetchone()[0]

                        if tested_count == len(target_card_ids):
                            result['test'].add(stage)
                            
                            # 満点判定（テスト完了後に全問正解かチェック）
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
                            
                            # 満点の場合は全学習完了とみなす
                            if perfect_count == len(target_card_ids):
                                result['perfect_completion'] = True
                                # 満点なので以降のステージの練習も完了扱い
                                for future_stage in range(stage, 4):
                                    result['practice'].add(future_stage)
                                break  # 満点なので以降のステージは不要

                    elif stage > 1:
                        # Stage 2, 3 で対象カードがない場合は前ステージで満点だった
                        result['test'].add(stage)
                        result['practice'].add(stage)

                # 満点でない場合の通常の練習完了判定
                if not result['perfect_completion']:
                    for stage in [1, 2, 3]:
                        if stage in result['test']:  # テストが完了している場合のみ
                            # 各ステージのテストで×だった問題を取得
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
                                # 練習で全問題が最終的に○になったかチェック
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
                                
                                # 全ての対象カードが練習で○になった場合に完了
                                if len(completed_practice_cards) == len(practice_target_cards):
                                    result['practice'].add(stage)
                            else:
                                # テストで×の問題がない場合（満点）は練習完了
                                result['practice'].add(stage)

    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result

@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')
    page_range = session.get('page_range', '').strip()
    stage = session.get('stage', 1)
    user_id = str(current_user.id)

    cards_dict = get_study_cards(source, stage, mode, page_range, user_id)

    if not cards_dict:
        flash("該当するカードが見つかりませんでした。")
        return redirect(url_for('prepare', source=source))

    return render_template('index.html', cards=cards_dict, mode=mode)


# ホームリダイレクト
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))


# ダッシュボード
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT DISTINCT source, subject, grade FROM image ORDER BY source')
                rows = cur.fetchall()
                sources = [{"source": r[0], "subject": r[1], "grade": r[2]} for r in rows]
                
                # 保存されたページ範囲を取得
                user_id = str(current_user.id)
                cur.execute('SELECT source, page_range FROM user_settings WHERE user_id = %s', (user_id,))
                saved_ranges = dict(cur.fetchall())
                
        return render_template('dashboard.html', sources=sources, saved_ranges=saved_ranges)
    except Exception as e:
        app.logger.error(f"ダッシュボード取得エラー: {e}")
        flash("教材一覧の取得に失敗しました")
        return redirect(url_for('login'))


@app.route('/set_page_range_and_prepare/<source>', methods=['POST'])
@login_required
def set_page_range_and_prepare(source):
    page_range = request.form.get('page_range', '').strip()
    user_id = str(current_user.id)
    
    # ページ範囲を保存
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO user_settings (user_id, source, page_range)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, source)
                    DO UPDATE SET page_range = EXCLUDED.page_range
                ''', (user_id, source, page_range))
                conn.commit()
    except Exception as e:
        app.logger.error(f"user_settings保存エラー: {e}")
        flash("設定の保存に失敗しました")
    
    return redirect(url_for('prepare', source=source))


# ログイン処理
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

    # --- POST時（学習設定の保存と遷移） ---
    if request.method == 'POST':
        page_range = request.form.get('page_range', '').strip()
        stage_mode = request.form.get('stage')

        if '-' in stage_mode:
            stage_str, mode = stage_mode.split('-')
            session['stage'] = int(stage_str)
            session['mode'] = mode
        else:
            flash("モード選択に不備があります")
            return redirect(url_for('prepare', source=source))

        session['page_range'] = page_range

        # user_settings に保存
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO user_settings (user_id, source, page_range)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, source)
                        DO UPDATE SET page_range = EXCLUDED.page_range
                    ''', (user_id, source, page_range))
                    conn.commit()
        except Exception as e:
            app.logger.error(f"user_settings保存エラー: {e}")

        return redirect(url_for('study', source=source))

    # --- GET時 ---
    saved_page_range = ''
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT page_range FROM user_settings
                    WHERE user_id = %s AND source = %s
                ''', (user_id, source))
                result = cur.fetchone()
                if result:
                    saved_page_range = result[0]
                    session['page_range'] = saved_page_range
    except Exception as e:
        app.logger.error(f"user_settings取得エラー: {e}")

    # ✅ GET時は completed を毎回取得
    try:
        completed_raw = get_completed_stages(user_id, source, saved_page_range)
        completed = {
            "test": set(completed_raw.get("test", [])),
            "practice": set(completed_raw.get("practice", [])),
            "perfect_completion": completed_raw.get("perfect_completion", False)
        }
        
        app.logger.error(f"[DEBUG] completed_raw: {completed_raw}")
        app.logger.error(f"[DEBUG] 最終的なcompleted: {completed}")
        app.logger.error(f"[DEBUG] perfect_completion: {completed_raw.get('perfect_completion', 'キーなし')}")
        
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")
        completed = {"test": set(), "practice": set(), "perfect_completion": False}

    # ← ここが重要！必ず return が実行される
    return render_template(
        'prepare.html',
        source=source,
        completed=completed,
        saved_page_range=saved_page_range
    )

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = data.get('stage')
    mode = data.get('mode')
    user_id = str(current_user.id)

    print(f"[LOG] user_id={user_id} card_id={card_id} result={result} stage={stage} mode={mode}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO study_log (user_id, card_id, result, stage, mode)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, card_id, result, stage, mode))
                conn.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        app.logger.error(f"ログ書き込みエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 新規登録
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

# ログアウト処理
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 履歴削除（教材単位）
@app.route('/reset_history/<source>', methods=['POST'])
@login_required
def reset_history(source):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    DELETE FROM study_log
                    WHERE user_id = %s AND card_id IN (
                        SELECT id FROM image WHERE source = %s
                    )
                ''', (str(current_user.id), source))
                conn.commit()
        flash(f"{source} の学習履歴を削除しました。")
    except Exception as e:
        app.logger.error(f"履歴削除エラー: {e}")
        flash("履歴の削除に失敗しました。")

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
