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

def parse_page_range(page_range_str):
    pages = set()
    for part in page_range_str.split(','):
        if '-' in part:
            start, end = part.split('-')
            pages.update(str(i) for i in range(int(start), int(end) + 1))
        else:
            pages.add(part.strip())
    return list(pages)

def get_completed_practice_stage(user_id, source, stage, page_numbers=None):
    """
    練習モードで、そのステージの全問題が known かどうかを判定。
    ページ範囲（page_numbers）が指定されている場合、それに限定して判定。
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 対象カードを取得
            if page_numbers:
                placeholders = ','.join(['%s'] * len(page_numbers))
                cur.execute(f'''
                    SELECT id FROM image
                    WHERE source = %s AND page_number IN ({placeholders})
                ''', [source] + page_numbers)
            else:
                cur.execute("SELECT id FROM image WHERE source = %s", (source,))
            valid_ids = {row[0] for row in cur.fetchall()}

            if not valid_ids:
                return False  # 出題カードが存在しない場合は未完了

            # 練習で known になったカード（ステージ単位）
            cur.execute("""
                SELECT DISTINCT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND result = 'known' AND mode = 'practice'
            """, (str(user_id), stage))
            known_cards = {row[0] for row in cur.fetchall()}

            # 対象カードのすべてが known になっていれば完了
            return valid_ids.issubset(known_cards)
        

def get_completed_stages(user_id, source, page_range):
    """ユーザー・教材・ページ範囲に対して完了した test/practice ステージを返す"""
    result = {'test': set(), 'practice': set()}
    user_id = str(user_id)

    # ページ範囲（例: '2-4,6'）→ ['2', '3', '4', '6']
    page_numbers = []
    if page_range:
        for part in page_range.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    page_numbers.extend([str(i) for i in range(int(start), int(end) + 1)])
                except ValueError:
                    continue
            else:
                page_numbers.append(part)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for mode in ['test', 'practice']:
                    cur.execute('''
                        SELECT stage, COUNT(DISTINCT card_id)
                        FROM study_log
                        WHERE user_id = %s AND mode = %s
                          AND result IN ('known', 'unknown')
                          AND card_id IN (
                              SELECT id FROM image
                              ... WHERE source = %s AND page_number::text = ANY(ARRAY[%s, %s, ...])
                          )
                        GROUP BY stage
                    ''', (user_id, mode, source, page_numbers))

                    for stage, count in cur.fetchall():
                        cur.execute('''
                            SELECT COUNT(*) FROM image
                            ... WHERE source = %s AND page_number::text = ANY(ARRAY[%s, %s, ...])

                        ''', (source, page_numbers))
                        total = cur.fetchone()[0]
                        if total > 0 and count == total:
                            result[mode].add(stage)

    except Exception as e:
        app.logger.error(f"完了ステージ取得エラー: {e}")

    return result


def get_completed_test_stages(user_id, source, page_numbers=None):
    completed = set()
    user_id_str = str(user_id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # すべての対象カード
                if page_numbers:
                    placeholders = ','.join(['%s'] * len(page_numbers))
                    cur.execute(f'''
                        SELECT id FROM image
                        WHERE source = %s AND page_number IN ({placeholders})
                    ''', [source] + page_numbers)
                else:
                    cur.execute('SELECT id FROM image WHERE source = %s', (source,))
                all_card_ids = [row[0] for row in cur.fetchall()]

                for stage in [1, 2, 3]:
                    if stage == 1:
                        target_ids = all_card_ids
                    else:
                        cur.execute('''
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND stage = %s AND result = 'unknown' AND mode = 'test'
                        ''', (user_id_str, stage - 1))
                        target_ids = [row[0] for row in cur.fetchall() if row[0] in all_card_ids]

                    if not target_ids:
                        continue

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


def is_practice_stage_completed(user_id, source, stage, page_numbers=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if page_numbers:
                placeholders = ','.join(['%s'] * len(page_numbers))
                cur.execute(f'''
                    SELECT id FROM image
                    WHERE source = %s AND page_number IN ({placeholders})
                ''', [source] + page_numbers)
                valid_ids = {row[0] for row in cur.fetchall()}
            else:
                cur.execute('SELECT id FROM image WHERE source = %s', (source,))
                valid_ids = {row[0] for row in cur.fetchall()}

            cur.execute('''
                SELECT DISTINCT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'test' AND result = 'unknown'
            ''', (str(user_id), stage))
            target_cards = {row[0] for row in cur.fetchall() if row[0] in valid_ids}

            if not target_cards:
                return False

            cur.execute('''
                SELECT DISTINCT card_id FROM study_log
                WHERE user_id = %s AND stage = %s AND mode = 'practice' AND result = 'known'
            ''', (str(user_id), stage))
            known_cards = {row[0] for row in cur.fetchall() if row[0] in valid_ids}

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

    # === GET時の処理 ===
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
                    session['page_range'] = saved_page_range  # セッションに反映
    except Exception as e:
        app.logger.error(f"user_settings取得エラー: {e}")

    # ✅ 完了判定に page_range を渡すよう修正
    completed = get_completed_stages(user_id, source, saved_page_range)

    return render_template(
        'prepare.html',
        source=source,
        completed=completed,
        saved_page_range=saved_page_range
    )


@app.route('/study/<source>')
@login_required
def study(source):
    mode = session.get('mode', 'test')  # 'test' or 'practice'
    page_range = session.get('page_range', '').strip()
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

                # ✅ page_range によるフィルタ処理（文字列型 page_number に対応）
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

                # ✅ 出題条件：mode × stage に応じたフィルタ
                if mode == 'test' and stage > 1:
                    # 前ステージの unknown のみ
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'test' AND result = 'unknown'
                        )
                    '''
                    params.extend([user_id, stage - 1])

                elif mode == 'practice':
                    # 同ステージ内の practice unknown のみ
                    query += '''
                        AND id IN (
                            SELECT card_id FROM study_log
                            WHERE user_id = %s AND stage = %s AND mode = 'practice' AND result = 'unknown'
                        )
                    '''
                    params.extend([user_id, stage])

                query += ' ORDER BY id DESC'
                cur.execute(query, params)
                records = cur.fetchall()

        if not records:
            flash("該当するカードが見つかりませんでした。")
            return redirect(url_for('prepare', source=source))

        # ✅ テンプレート向けに辞書形式で整形
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
