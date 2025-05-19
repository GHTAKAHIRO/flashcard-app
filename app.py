from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os
from dotenv import load_dotenv
import logging

# .envファイルの読み込み
load_dotenv(dotenv_path='dbname.env')

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'

# ロギング設定
logging.basicConfig(level=logging.DEBUG)

# Flask-Login初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# DB接続設定
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

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password_hash FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return User(*user)
    return None

@app.route('/')
@login_required
def index():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer
                    FROM image ORDER BY id DESC
                ''')
                cards = cur.fetchall()
                cards_dict = []
                for c in cards:
                    cards_dict.append({
                        'id': c[0], 'subject': c[1], 'grade': c[2], 'source': c[3],
                        'page_number': c[4], 'problem_number': c[5], 'topic': c[6],
                        'level': c[7], 'format': c[8], 'image_problem': c[9], 'image_answer': c[10]
                    })
        return render_template('index.html', cards=cards_dict)
    except Exception as e:
        app.logger.error(f"エラーが発生しました: {e}")
        flash('データベースの取得に失敗しました。')
        return redirect(url_for('index'))

@app.route('/log_result', methods=['POST'])
@login_required
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    user_id = current_user.id

    app.logger.debug(f"受け取ったデータ: {data}")

    if not card_id or not result:
        app.logger.error("必要なデータが不足しています")
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO study_log (user_id, card_id, result) VALUES (%s, %s, %s)
        ''', (user_id, card_id, result))
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info("データベースに書き込み成功")
        return jsonify({'status': 'ok'})
    except Exception as e:
        app.logger.error(f"DB書き込みエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"登録エラー: {e}")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[2], password):
            login_user(User(*user))
            return redirect(url_for('index'))
        flash('ログインに失敗しました')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)