# 🔽 HEAD部分はそのまま使えます（from～環境変数）

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

def get_completed_stages(user_id, source):
    """指定されたユーザー・教材について、完了したステージ（test/practice）を返す"""
    result = {'test': set(), 'practice': set()}

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for mode in ['test', 'practice']:
                cur.execute("""
                    SELECT DISTINCT stage
                    FROM study_log
                    WHERE user_id = %s
                      AND card_id IN (
                          SELECT id FROM image WHERE source = %s
                      )
                      AND result = 'known'
                      AND mode = %s
                      AND stage IS NOT NULL
                """, (str(user_id), source, mode))

                rows = cur.fetchall()
                result[mode] = {r[0] for r in rows}

    return result

def get_completed_test_stages(user_id, source):
    """指定されたユーザー・教材について、完了したテストステージを返す"""
    completed = set()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for stage in [1, 2, 3]:
                    cur.execute("SELECT COUNT(*) FROM image WHERE source = %s", (source,))
                    total = cur.fetchone()[0]
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id) FROM study_log
                        WHERE user_id = %s AND stage = %s AND result IN ('known', 'unknown')
                          AND card_id IN (SELECT id FROM image WHERE source = %s)
                    ''', (str(user_id), stage, source))
                    answered = cur.fetchone()[0]
                    if total > 0 and total == answered:
                        completed.add(stage)
    except Exception as e:
        app.logger.error(f"完了済みテスト判定エラー: {e}")
    return completed

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
        return render_template('dashboard.html', sources=sources)
    except Exception as e:
        app.logger.error(f"ダッシュボード取得エラー: {e}")
        flash("教材一覧の取得に失敗しました")
        return redirect(url_for('login'))

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
    if request.method == 'POST':
        page_range = request.form.get('page_range')
        stage_mode = request.form.get('stage')
        if '-' in stage_mode:
            stage_str, mode = stage_mode.split('-')
            session['stage'] = int(stage_str)
            session['mode'] = mode
        else:
            flash("モード選択に不備があります")
            return redirect(url_for('prepare', source=source))

        session['page_range'] = page_range
        return redirect(url_for('study', source=source))

    # ✅ ここで完了ステータスを取得
    completed = get_completed_stages(current_user.id, source)
    return render_template('prepare.html', source=source, completed=completed)


    # ✅ 学習済みテストステージをチェック
    completed_tests = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for stage_num in [1, 2, 3]:
                    # 指定教材のカード数を取得
                    cur.execute('''
                        SELECT COUNT(*) FROM image
                        WHERE source = %s
                    ''', (source,))
                    total_cards = cur.fetchone()[0]

                    # 対象ステージの known + unknown の記録数を取得（重複除外）
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id) FROM study_log
                        WHERE user_id = %s AND stage = %s AND result IN ('known', 'unknown')
                        AND card_id IN (SELECT id FROM image WHERE source = %s)
                    ''', (user_id, stage_num, source))
                    answered = cur.fetchone()[0]

                    if total_cards > 0 and answered == total_cards:
                        completed_tests.append(stage_num)

    except Exception as e:
        app.logger.error(f"完了済みテスト判定エラー: {e}")
        flash("テスト完了チェックでエラーが発生しました")

    return render_template('prepare.html', source=source, completed_tests=completed_tests)


@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')  # 'test' または 'practice'
    page_range = session.get('page_range')
    stage = session.get('stage', 1)
    user_id = str(current_user.id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = '''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image
                    WHERE source = %s
                '''
                params = [source]

                # ✅ 出題対象を分ける
                if mode == 'test' and stage > 1:
                    # 前回のテストで間違えた問題のみ対象
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND result = 'unknown' AND stage = %s
                        )
                    '''
                    params.extend([user_id, stage - 1])
                elif mode == 'practice':
                    # 前回のテストで間違えた問題だけ練習
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND result = 'unknown' AND stage = %s
                        )
                    '''
                    params.extend([user_id, stage - 1])
                # stage==1 の test の場合は全件対象（条件追加なし）

                query += ' ORDER BY id DESC'
                cur.execute(query, params)
                records = cur.fetchall()

        if not records:
            flash("該当するカードが見つかりませんでした。")
            return redirect(url_for('prepare', source=source))

        cards_dict = [dict(
            id=r[0], subject=r[1], grade=r[2], source=r[3],
            page_number=r[4], problem_number=r[5], topic=r[6],
            level=r[7], format=r[8], image_problem=r[9], image_answer=r[10]
        ) for r in records]

        return render_template('index.html', cards=cards_dict, mode=mode)

    except Exception as e:
        app.logger.error(f"教材取得エラー: {e}")
        flash("データの取得に失敗しました")
        return redirect(url_for('dashboard'))


@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    stage = session.get('stage', 1)
    user_id = str(current_user.id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO study_log (user_id, card_id, result, stage)
                    VALUES (%s, %s, %s, %s)
                ''', (user_id, card_id, result, stage))
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
