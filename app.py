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

def get_completed_practice_stage(user_id, source, stage):
    """
    練習モードで、そのステージの全問題が known かどうかを判定
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 対象教材の全カード数
            cur.execute("SELECT COUNT(*) FROM image WHERE source = %s", (source,))
            total = cur.fetchone()[0]

            # 練習で known になったカード数（ステージ単位）
            cur.execute("""
                SELECT COUNT(DISTINCT card_id) FROM study_log
                WHERE user_id = %s AND stage = %s AND result = 'known' AND mode = 'practice'
                AND card_id IN (SELECT id FROM image WHERE source = %s)
            """, (str(user_id), stage, source))
            known = cur.fetchone()[0]

            return total > 0 and known == total

def get_completed_stages(user_id, source):
    result = {'test': set(), 'practice': set()}
    user_id_str = str(user_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for stage in [1, 2, 3]:
                # ✅ テスト完了判定
                if stage == 1:
                    cur.execute('SELECT id FROM image WHERE source = %s', (source,))
                    target_test = {row[0] for row in cur.fetchall()}
                else:
                    cur.execute('''
                        SELECT card_id FROM study_log
                        WHERE user_id = %s AND stage = %s AND result = 'unknown' AND mode = 'test'
                        AND card_id IN (SELECT id FROM image WHERE source = %s)
                    ''', (user_id_str, stage - 1, source))
                    target_test = {row[0] for row in cur.fetchall()}

                if target_test:
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id) FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test'
                        AND card_id = ANY(%s)
                    ''', (user_id_str, stage, list(target_test)))
                    answered = cur.fetchone()[0]
                    if answered == len(target_test):
                        result['test'].add(stage)

                # ✅ 練習完了判定（テストで×だったカードがすべて練習で○になったか）
                cur.execute('''
                    SELECT card_id FROM study_log
                    WHERE user_id = %s AND stage = %s AND result = 'unknown' AND mode = 'test'
                    AND card_id IN (SELECT id FROM image WHERE source = %s)
                ''', (user_id_str, stage, source))
                target_practice = {row[0] for row in cur.fetchall()}

                if target_practice:
                    cur.execute('''
                        SELECT card_id FROM study_log
                        WHERE user_id = %s AND stage = %s AND result = 'known' AND mode = 'practice'
                        AND card_id IN (SELECT id FROM image WHERE source = %s)
                    ''', (user_id_str, stage, source))
                    known_cards = {row[0] for row in cur.fetchall()}

                    if target_practice.issubset(known_cards):
                        result['practice'].add(stage)

    return result


def get_completed_test_stages(user_id, source):
    """
    各ステージのテストが完了したかどうかを返す（ステージ1は全件、2以降は前ステージの✕のみ対象）
    """
    completed = set()
    user_id_str = str(user_id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for stage in [1, 2, 3]:
                    if stage == 1:
                        # ステージ1：教材内の全カードが対象
                        cur.execute('''
                            SELECT id FROM image WHERE source = %s
                        ''', (source,))
                        target_ids = [row[0] for row in cur.fetchall()]
                    else:
                        # ステージ2, 3：前ステージのテストで✕だったカードのみ対象
                        cur.execute('''
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND stage = %s AND result = 'unknown' AND mode = 'test'
                              AND card_id IN (SELECT id FROM image WHERE source = %s)
                        ''', (user_id_str, stage - 1, source))
                        target_ids = [row[0] for row in cur.fetchall()]

                    if not target_ids:
                        continue  # 出題対象がなければ完了ステージにはしない

                    # このステージで解答済みのカード（known/unknown 問わず）
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id) FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'test'
                          AND card_id = ANY(%s)
                    ''', (user_id_str, stage, target_ids))
                    answered = cur.fetchone()[0]

                    if answered == len(target_ids):
                        completed.add(stage)

    except Exception as e:
        app.logger.error(f"完了済みテスト判定エラー: {e}")

    return completed


def is_practice_stage_completed(user_id, source, stage):
    """
    ステージNの練習が完了したか（= テストで✕だったカードが練習で全て○になったか）
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # テストで間違えたカード（対象）
            cur.execute('''
                SELECT DISTINCT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'test' AND result = 'unknown'
                AND card_id IN (SELECT id FROM image WHERE source = %s)
            ''', (str(user_id), stage, source))
            target_cards = {row[0] for row in cur.fetchall()}

            if not target_cards:
                return False  # テストで✕のカードがないなら未完了とみなす

            # 練習で○になったカード（同じステージ内）
            cur.execute('''
                SELECT DISTINCT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'practice' AND result = 'known'
                AND card_id IN (SELECT id FROM image WHERE source = %s)
            ''', (str(user_id), stage, source))
            known_cards = {row[0] for row in cur.fetchall()}

            return target_cards.issubset(known_cards)


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
    user_id = str(current_user.id)

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

        # ✅ user_settingsに保存または更新
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

    # ✅ GET時: 以前保存されたページ範囲を取得
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
    except Exception as e:
        app.logger.error(f"user_settings取得エラー: {e}")

    # ✅ テスト・練習の完了状況を取得
    completed = get_completed_stages(user_id, source)

    return render_template('prepare.html', source=source, completed=completed, saved_page_range=saved_page_range)


@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')
    stage = session.get('stage', 1)
    source = source
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

                if mode == 'test' and stage > 1:
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND result = 'unknown' AND stage = %s AND mode = 'test'
                        )
                    '''
                    params.extend([user_id, stage - 1])

                elif mode == 'practice':
                    # ✕のまま残っているカードだけ再出題
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND result = 'unknown' AND stage = %s AND mode = 'test'
                            EXCEPT
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND result = 'known' AND stage = %s AND mode = 'practice'
                        )
                    '''
                    params.extend([user_id, stage, user_id, stage])

                query += ' ORDER BY id DESC'
                cur.execute(query, params)
                records = cur.fetchall()


        if not records:
            flash("該当するカードが見つかりませんでした。")
            return redirect(url_for('prepare', source=source))

        # ✅ テンプレートに渡す形式に整形
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
    mode = session.get('mode', 'test')  # ✅ 'test' か 'practice'
    user_id = str(current_user.id)

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
