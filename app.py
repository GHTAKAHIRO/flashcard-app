from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv(dotenv_path='dbname.env')

# Flaskアプリケーションのインスタンス作成
app = Flask(__name__)
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
    """データベースからカード情報を取得して表示"""
    conn = get_db_connection()
    cur = conn.cursor()

    # データベースからデータを取得
    cur.execute('''SELECT id, subject, grade, source, page_number, problem_number, topic, level, format, image_problem, image_answer 
                   FROM image ORDER BY id DESC''')
    cards = cur.fetchall()

    # データを辞書形式に変換
    cards_dict = []
    for c in cards:
        cards_dict.append({
            'id': c[0],
            'subject': c[1],
            'grade': c[2],
            'source': c[3],
            'page_number': c[4],
            'problem_number': c[5],
            'topic': c[6],
            'level': c[7],
            'format': c[8],
            'image_problem': c[9],  # WasabiのURL
            'image_answer': c[10]   # WasabiのURL
        })
    
    cur.close()
    conn.close()

    return render_template('index.html', cards=cards_dict)

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

if __name__ == '__main__':
    app.run(debug=True)
