from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS  # Import CORS
import psycopg2
import os
from dotenv import load_dotenv
import logging  # ロギングのインポート

# .envファイルを読み込む
load_dotenv(dotenv_path='dbname.env')

# Flaskアプリケーションのインスタンス作成
app = Flask(__name__)

# ログ設定
logging.basicConfig(level=logging.DEBUG)

app.secret_key = 'your_secret_key'  # フラッシュメッセージ用

# 環境変数からデータベース接続情報を取得
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# データベース接続の設定
def get_db_connection():
    """データベースへの接続を取得"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.route('/')
def index():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT ...')
                cards = cur.fetchall()
                cards_dict = [ ... ]
        return render_template('index.html', cards=cards_dict)  # ✅ 関数内
    except Exception as e:
        app.logger.error(f"エラーが発生しました: {e}")
        flash('データベースの取得に失敗しました。')
        return redirect(url_for('index'))

@app.route('/add', methods=['GET', 'POST'])
def add_card():
    if request.method == 'POST':
        # フォームデータの取得
        subject = request.form['subject']
        grade = request.form['grade']
        source = request.form['source']
        page_number = request.form['page_number']
        problem_number = request.form['problem_number']
        topic = request.form['topic']
        level = request.form['level']
        format = request.form['format']
        
        # 画像ファイルの取得
        q_image_file = request.files.get('question_image')
        a_image_file = request.files.get('answer_image')

        q_image_url = None
        a_image_url = None

        # 画像ファイルがあればS3にアップロードしてURLを取得
        if q_image_file and q_image_file.filename:
            q_image_url = upload_file_to_s3(q_image_file, 'question')

        if a_image_file and a_image_file.filename:
            a_image_url = upload_file_to_s3(a_image_file, 'answer')

        # データベースに保存
        save_card_to_db(subject, grade, source, page_number, problem_number, topic, level, format, q_image_url, a_image_url)

        flash('カードを追加しました！')
        return redirect(url_for('add_card'))  # フォームの再表示

    return render_template('add.html')  # フォームページを表示

@app.route('/log_result', methods=['POST'])
def log_result():
    data = request.get_json()
    card_id = data.get('card_id')
    result = data.get('result')
    user_id = 'guest'

    # 受け取ったデータをデバッグログに記録
    app.logger.debug(f"受け取ったデータ: {data}")

    if not card_id or not result:
        app.logger.error("必要なデータが不足しています")
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        # データベースに接続し、ログ記録
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''INSERT INTO study_log (user_id, card_id, result) VALUES (%s, %s, %s)''', (user_id, card_id, result))
        conn.commit()
        cur.close()
        conn.close()

        # データベースに書き込み成功した場合のログ
        app.logger.info("データベースに書き込み成功")
        return jsonify({'status': 'ok'})
    except Exception as e:
        # 例外発生時のログ
        app.logger.error(f"DB書き込みエラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render 用
    app.run(host="0.0.0.0", port=port)
S