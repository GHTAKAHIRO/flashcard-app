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

def get_study_cards(source, stage, mode, page_range, user_id, difficulty=''):
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

                # 難易度フィルタの追加
                if difficulty:
                    difficulty_list = [d.strip() for d in difficulty.split(',')]
                    difficulty_placeholders = ','.join(['%s'] * len(difficulty_list))
                    query += f' AND level IN ({difficulty_placeholders})'
                    params.extend(difficulty_list)

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
    

def get_completed_stages(user_id, source, page_range, difficulty=''):  # difficulty引数追加
    # 関数内で画像を取得する部分
    if page_numbers:
        cur.execute('''
            SELECT id FROM image
            WHERE source = %s AND page_number::text = ANY(%s)
        ''', (source, page_numbers))
    else:
        cur.execute('SELECT id FROM image WHERE source = %s', (source,))
    
    # 難易度フィルタを追加
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


@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')
    page_range = session.get('page_range', '').strip()
    difficulty = session.get('difficulty', '').strip()  # 追加
    stage = session.get('stage', 1)
    user_id = str(current_user.id)

    cards_dict = get_study_cards(source, stage, mode, page_range, user_id, difficulty)  # difficulty追加

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
                
                # 保存されたページ範囲と難易度を取得
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
    difficulty_list = request.form.getlist('difficulty')  # チェックボックスの値を取得
    difficulty = ','.join(difficulty_list) if difficulty_list else ''
    user_id = str(current_user.id)
    
    # ページ範囲と難易度を保存
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
    difficulty_list = request.form.getlist('difficulty')
    difficulty = ','.join(difficulty_list) if difficulty_list else ''
    stage_mode = request.form.get('stage')

    # stage_mode の None チェック
    if not stage_mode or '-' not in stage_mode:
        flash("学習ステージを選択してください")
        return redirect(url_for('prepare', source=source))

    stage_str, mode = stage_mode.split('-')
    session['stage'] = int(stage_str)
    session['mode'] = mode
    session['page_range'] = page_range
    session['difficulty'] = difficulty  # 追加

    # user_settings に保存
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

    # --- GET時 ---
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
                    session['difficulty'] = saved_difficulty  # セッションにも保存
    except Exception as e:
        app.logger.error(f"user_settings取得エラー: {e}")
        
    try:
        completed_raw = get_completed_stages(user_id, source, saved_page_range, saved_difficulty)  # difficulty追加
        completed = {
            "test": set(completed_raw.get("test", [])),
            "practice": set(completed_raw.get("practice", [])),
            "perfect_completion": completed_raw.get("perfect_completion", False),
            "practice_history": completed_raw.get("practice_history", {})
        }
        
        # デバッグ用ログ
        app.logger.error(f"[DEBUG] practice_history: {completed.get('practice_history', {})}")
        app.logger.error(f"[DEBUG] completed_raw全体: {completed_raw}")
        
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")
        completed = {"test": set(), "practice": set(), "perfect_completion": False, "practice_history": {}}

    return render_template(
        'prepare.html',
        source=source,
        completed=completed,
        saved_page_range=saved_page_range,
        saved_difficulty=saved_difficulty  # 追加
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
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 削除前の件数確認
                cur.execute('''
                    SELECT COUNT(*) FROM study_log
                    WHERE user_id = %s AND card_id IN (
                        SELECT id FROM image WHERE source = %s
                    )
                ''', (user_id, source))
                before_count = cur.fetchone()[0]
                
                # 削除実行
                cur.execute('''
                    DELETE FROM study_log
                    WHERE user_id = %s AND card_id IN (
                        SELECT id FROM image WHERE source = %s
                    )
                ''', (user_id, source))
                
                deleted_count = cur.rowcount
                conn.commit()
                
                
        flash(f"{source} の学習履歴を削除しました。")
    except Exception as e:
        app.logger.error(f"履歴削除エラー: {e}")
        import traceback
        app.logger.error(f"[DEBUG] スタックトレース: {traceback.format_exc()}")
        flash("履歴の削除に失敗しました。")

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
