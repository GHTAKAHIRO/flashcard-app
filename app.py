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

def build_test_filter_subquery(stage, user_id):
    if stage == 1:
        return '', []
    else:
        return '''
            AND id IN (
                SELECT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'test' AND result = 'unknown'
            )
        ''', [user_id, stage - 1]

def build_practice_filter_subquery(stage, user_id):
    return '''
        AND id IN (
            SELECT card_id FROM (
                SELECT DISTINCT ON (card_id) card_id, result
                FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'practice'
                ORDER BY card_id, id DESC
            ) AS latest
            WHERE result = 'unknown'
        )
    ''', [user_id, stage]


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

                # --- ページ範囲条件の追加 ---
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

                # --- モード別フィルター ---
                if mode == 'test':
                    if stage > 1:
                        query += '''
                            AND id IN (
                                SELECT card_id FROM study_log
                                WHERE user_id = %s AND stage = %s AND mode = 'test' AND result = 'unknown'
                            )
                        '''
                        params.extend([user_id, stage - 1])
                elif mode == 'practice':
                    # 該当ステージでの練習ログが存在するか確認
                    cur.execute('''
                        SELECT COUNT(*) FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'practice'
                    ''', (user_id, stage))
                    practice_log_count = cur.fetchone()[0]

                    if practice_log_count == 0:
                        # 初回練習：前のテストでunknownだったカード
                        query += '''
                            AND id IN (
                                SELECT card_id FROM (
                                    SELECT DISTINCT ON (card_id) card_id, result
                                    FROM study_log
                                    WHERE user_id = %s AND stage = %s AND mode = 'test'
                                    ORDER BY card_id, id DESC
                                ) AS latest
                                WHERE result = 'unknown'
                            )
                        '''
                        params.extend([user_id, stage])
                    else:
                        # 2周目以降：この練習内で最新が unknown のみ
                        query += '''
                            AND id IN (
                                SELECT card_id FROM (
                                    SELECT DISTINCT ON (card_id) card_id, result
                                    FROM study_log
                                    WHERE user_id = %s AND stage = %s AND mode = 'practice'
                                    ORDER BY card_id, id DESC
                                ) AS latest
                                WHERE result = 'unknown'
                            )
                        '''
                        params.extend([user_id, stage])

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
    result = {'test': set(), 'practice': set()}
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
                if page_numbers:
                    cur.execute('''
                        SELECT id FROM image
                        WHERE source = %s AND page_number::text = ANY(%s)
                    ''', (source, page_numbers))
                else:
                    cur.execute('SELECT id FROM image WHERE source = %s', (source,))
                card_ids = [row[0] for row in cur.fetchall()]

                if not card_ids:
                    return result

                for stage in [1, 2, 3]:
                    # test完了：全カードにログがある
                    cur.execute('''
                        SELECT COUNT(DISTINCT card_id) FROM study_log
                        WHERE user_id = %s AND mode = 'test' AND stage = %s AND card_id = ANY(%s)
                    ''', (user_id, stage, card_ids))
                    count = cur.fetchone()[0]
                    if count == len(card_ids):
                        result['test'].add(stage)

                    # practice完了：このステージでunknownがない
                    cur.execute('''
                        SELECT DISTINCT ON (card_id) card_id, result
                        FROM study_log
                        WHERE user_id = %s AND stage = %s AND mode = 'practice'
                        ORDER BY card_id, id DESC
                    ''', (user_id, stage))
                    latest_results = {r[0]: r[1] for r in cur.fetchall() if r[0] in card_ids}

                    if all(res == 'known' for res in latest_results.values()) and latest_results:
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
                    session['page_range'] = saved_page_range  # セッションにも反映
    except Exception as e:
        app.logger.error(f"user_settings取得エラー: {e}")

    # ✅ GET時は completed を毎回取得（例外関係なく）
    try:
        completed_raw = get_completed_stages(user_id, source, saved_page_range)
        completed = {
            "test": set(completed_raw.get("test", [])),
            "practice": set(completed_raw.get("practice", []))
        }
    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")
        completed = {"test": set(), "practice": set()}

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
