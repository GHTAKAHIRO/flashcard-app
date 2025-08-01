# ========== Redis除去版 パート1: 基本設定・インポート・初期化 ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import math
# PostgreSQL関連のインポート
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps
import json
import hashlib
import threading
import time
import queue
import psycopg2.pool
from contextlib import contextmanager
import atexit
from flask_wtf.csrf import CSRFProtect
import io
import csv
import re
# import boto3  # AWS S3関連（現在は使用しない）
# from botocore.exceptions import ClientError  # AWS S3関連（現在は使用しない）
# from PIL import Image  # 画像処理（現在は使用しない）
import uuid
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.study import study_bp
from routes.choice_studies import choice_studies_bp
from models.user import User
from utils.db import get_db_connection, get_db_cursor

# ========== 設定エリア ==========
# ローカル開発用の環境変数ファイルを読み込み（本番環境では無視される）
load_dotenv(dotenv_path='dbname.env')

# 環境変数の確認とログ出力
print("🔍 環境変数チェック:")
print(f"DB_TYPE: {os.getenv('DB_TYPE', 'sqlite')}")
print(f"DB_PATH: {os.getenv('DB_PATH', 'flashcards.db')}")
print(f"DB_HOST: {os.getenv('DB_HOST', 'Not set')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 'Not set')}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'Not set')}")
print(f"DB_USER: {os.getenv('DB_USER', 'Not set')}")
print(f"DB_PASSWORD: {'Set' if os.getenv('DB_PASSWORD') else 'Not set'}")
print(f"WASABI_ACCESS_KEY: {'Set' if os.getenv('WASABI_ACCESS_KEY') else 'Not set'}")
print(f"WASABI_SECRET_KEY: {'Set' if os.getenv('WASABI_SECRET_KEY') else 'Not set'}")
print(f"WASABI_BUCKET: {os.getenv('WASABI_BUCKET', 'Not set')}")
print(f"WASABI_ENDPOINT: {os.getenv('WASABI_ENDPOINT', 'Not set')}")

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'
# csrf = CSRFProtect(app)  # 本番環境ではCSRF保護を無効化

# CSRFトークンを空文字列として提供（テンプレート互換性のため）
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=lambda: '')
logging.basicConfig(level=logging.INFO)

app.config.update(
    # JSON処理高速化
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=False,
    
    # セッション最適化
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    
    # 静的ファイルキャッシュとパフォーマンス最適化
    SEND_FILE_MAX_AGE_DEFAULT=31536000,  # 1年
    TEMPLATES_AUTO_RELOAD=False,
    
    # データベース設定
    DB_TYPE=os.getenv('DB_TYPE', 'sqlite'),
    DB_PATH=os.getenv('DB_PATH', 'flashcards.db'),
    DB_HOST=os.getenv('DB_HOST'),
    DB_PORT=os.getenv('DB_PORT'),
    DB_NAME=os.getenv('DB_NAME'),
    DB_USER=os.getenv('DB_USER'),
    DB_PASSWORD=os.getenv('DB_PASSWORD')
)

print("🚀 バックエンド高速化システム初期化完了")

# Flask-Login 初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Blueprint登録
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(study_bp)
app.register_blueprint(choice_studies_bp)

# --- ここからカスタムフィルタ追加 ---
def to_kanji_circle(value):
    kanji_circles = {
        1: '①', 2: '②', 3: '③', 4: '④', 5: '⑤',
        6: '⑥', 7: '⑦', 8: '⑧', 9: '⑨', 10: '⑩'
    }
    try:
        return kanji_circles.get(int(value), str(value))
    except Exception:
        return str(value)

app.jinja_env.filters['to_kanji_circle'] = to_kanji_circle
# --- カスタムフィルタここまで ---

# Jinja2フィルターを追加
@app.template_filter('int_to_letter')
def int_to_letter(value):
    """数字を文字（A, B, C, D...）に変換"""
    if isinstance(value, int) and 1 <= value <= 26:
        return chr(64 + value)  # A=65, B=66, ...
    return str(value)

# 🚀 非同期ログ処理システム
log_queue = queue.Queue(maxsize=1000)
log_worker_active = True

def log_worker():
    """バックグラウンドでログを処理するワーカー"""
    while log_worker_active:
        try:
            log_data = log_queue.get(timeout=1)
            if log_data is None:  # 終了シグナル
                break
            
            user_id, card_id, result, stage, mode = log_data
            
            try:
                with get_db_connection() as conn:
                    with get_db_cursor(conn) as cur:
                        cur.execute('''
                            INSERT INTO study_log (user_id, card_id, result, stage, mode)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (user_id, card_id, result, stage, mode))
                        conn.commit()
                app.logger.info(f"非同期ログ記録完了: user={user_id}, card={card_id}")
            except Exception as e:
                app.logger.error(f"非同期ログ書き込みエラー: {e}")
            finally:
                log_queue.task_done()
                
        except queue.Empty:
            continue
        except Exception as e:
            app.logger.error(f"ログワーカーエラー: {e}")

# ワーカースレッド開始
log_thread = threading.Thread(target=log_worker, daemon=True)
log_thread.start()

# Wasabi S3クライアント初期化
def init_wasabi_client():
    """Wasabi S3クライアントの初期化（現在は無効化）"""
    print("⚠️ Wasabi S3クライアントは現在無効化されています")
    return None

def get_unit_image_folder_path(question_id):
    """問題IDから単元の章番号に基づいて画像フォルダパスを生成"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題の単元情報を取得
                cur.execute('''
                    SELECT 
                        t.subject, 
                        t.wasabi_folder_path,
                        u.chapter_number
                    FROM input_questions q
                    JOIN input_units u ON q.unit_id = u.id
                    JOIN input_textbooks t ON u.textbook_id = t.id
                    WHERE q.id = ?
                ''', (question_id,))
                result = cur.fetchone()
                
                if result:
                    subject, textbook_folder, chapter_number = result
                    
                    # Noneや空の場合はデフォルト値を使用
                    base_folder = textbook_folder or 'so-image'
                    
                    # 科目を英語に変換
                    subject_map = {
                        '地理': 'geography',
                        '歴史': 'history',
                        '公民': 'civics',
                        '理科': 'science'
                    }
                    subject_en = subject_map.get(subject, 'other')
                    
                    # 章番号が設定されている場合は章番号を使用、そうでなければデフォルト
                    if chapter_number:
                        folder_path = f"{base_folder}/{subject_en}/{chapter_number}"
                    else:
                        folder_path = f"{base_folder}/{subject_en}/default"
                    
                    print(f"🔍 生成されたフォルダパス: {folder_path}")
                    return folder_path
                else:
                    # 単元が設定されていない場合はデフォルトパス
                    print(f"⚠️ 問題ID {question_id} の単元情報が見つかりません")
                    return "social_studies/default"
                    
    except Exception as e:
        app.logger.error(f"フォルダパス生成エラー: {e}")
        return "social_studies/default"

def get_unit_image_folder_path_by_unit_id(unit_id):
    """単元IDから教材のWasabiフォルダパスと章番号に基づいて画像フォルダパスを生成"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元情報と教材のWasabiフォルダパスを取得
                cur.execute('''
                    SELECT 
                        t.subject, 
                        t.wasabi_folder_path,
                        u.chapter_number
                    FROM input_units u
                    JOIN input_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = ?
                ''', (unit_id,))
                result = cur.fetchone()
                
                if result:
                    subject, wasabi_folder_path, chapter_number = result
                    
                    # Noneや空の場合はデフォルト値を使用
                    base_folder = wasabi_folder_path or 'so-image'
                    
                    # 章番号が設定されている場合は章番号を使用、そうでなければデフォルト
                    if chapter_number:
                        folder_path = f"{base_folder}/{chapter_number}"
                    else:
                        # フォールバック: 科目を英語に変換
                        subject_map = {
                            '地理': 'geography',
                            '歴史': 'history',
                            '公民': 'civics',
                            '理科': 'science'
                        }
                        subject_en = subject_map.get(subject, 'other')
                        base_folder = 'so-image'
                        if chapter_number:
                            folder_path = f"{base_folder}/{subject_en}/{chapter_number}"
                        else:
                            folder_path = f"{base_folder}/{subject_en}/default"
                    
                    print(f"🔍 単元ID {unit_id} から生成されたフォルダパス: {folder_path}")
                    return folder_path
                else:
                    # 単元が見つからない場合はデフォルトパス
                    print(f"⚠️ 単元ID {unit_id} が見つかりません")
                    return "social_studies/default"
                    
    except Exception as e:
        app.logger.error(f"フォルダパス生成エラー: {e}")
        return "social_studies/default"

# 画像アップロード関数
def upload_image_to_wasabi(image_file, question_id, textbook_id=None):
    """画像をWasabiにアップロード（現在は無効化）"""
    print("⚠️ 画像アップロード機能は現在無効化されています")
    return None, "画像アップロード機能は現在無効化されています"

def set_image_public_access(image_url):
    """既存の画像ファイルに公開アクセス権限を設定（現在は無効化）"""
    print("⚠️ 画像公開アクセス設定は現在無効化されています")
    return None

@app.route('/social_studies/api/check_image')
def social_studies_check_image():
    """画像存在確認API"""
    try:
        image_name = request.args.get('image_name', '').strip()
        unit_id = request.args.get('unit_id', '').strip()
        
        if not image_name or not unit_id:
            return jsonify({
                'error': 'image_nameとunit_idが必要です',
                'exists': False
            }), 400
        
        # 単元IDから画像フォルダパスを取得
        folder_path = get_unit_image_folder_path_by_unit_id(int(unit_id))
        
        # 画像URLを構築（Wasabi S3のURL形式）
        base_url = "https://s3.ap-northeast-1-ntt.wasabisys.com/so-image"
        
        # 画像名に拡張子がない場合は.jpgを追加
        if not any(image_name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            image_name = f"{image_name}.jpg"
        
        # 完全な画像URLを構築
        image_url = f"{base_url}/{folder_path}/{image_name}"
        
        # 画像の存在確認（実際のHTTPリクエストは行わず、URLを返す）
        # 実際の環境では、Wasabi S3のHEADリクエストで存在確認を行うことができます
        
        return jsonify({
            'exists': True,  # 実際の確認は行わず、常にTrueを返す
            'image_url': image_url,
            'folder_path': folder_path,
            'message': '画像が見つかりました'
        })
        
    except Exception as e:
        app.logger.error(f"画像確認APIエラー: {e}")
        return jsonify({
            'error': '画像確認に失敗しました',
            'exists': False
        }), 500

@app.route('/social_studies/api/textbooks')
def social_studies_api_textbooks():
    """教材一覧取得API"""
    try:
        subject = request.args.get('subject', '').strip()
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                if subject:
                    cur.execute('''
                        SELECT id, name, subject, grade, publisher, description, wasabi_folder_path
                        FROM input_textbooks 
                        WHERE subject = ?
                        ORDER BY name
                    ''', (subject,))
                else:
                    cur.execute('''
                        SELECT id, name, subject, grade, publisher, description, wasabi_folder_path
                        FROM input_textbooks 
                        ORDER BY subject, name
                    ''')
                
                textbooks = []
                for row in cur.fetchall():
                    textbooks.append({
                        'id': row[0],
                        'name': row[1],
                        'subject': row[2],
                        'grade': row[3],
                        'publisher': row[4],
                        'description': row[5],
                        'wasabi_folder_path': row[6]
                    })
                
                return jsonify(textbooks)
                
    except Exception as e:
        app.logger.error(f"教材一覧取得APIエラー: {e}")
        return jsonify({'error': '教材一覧の取得に失敗しました'}), 500

@app.route('/social_studies/api/textbook/<int:textbook_id>')
def social_studies_api_textbook(textbook_id):
    """教材詳細取得API"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, name, subject, grade, publisher, description, wasabi_folder_path
                    FROM input_textbooks 
                    WHERE id = ?
                ''', (textbook_id,))
                
                row = cur.fetchone()
                if not row:
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                textbook = {
                    'id': row[0],
                    'name': row[1],
                    'subject': row[2],
                    'grade': row[3],
                    'publisher': row[4],
                    'description': row[5],
                    'wasabi_folder_path': row[6]
                }
                
                return jsonify(textbook)
                
    except Exception as e:
        app.logger.error(f"教材詳細取得APIエラー: {e}")
        return jsonify({'error': '教材詳細の取得に失敗しました'}), 500

@app.route('/social_studies/api/units')
def social_studies_api_units():
    """単元一覧取得API"""
    try:
        textbook_id = request.args.get('textbook_id', '').strip()
        
        if not textbook_id:
            return jsonify({'error': 'textbook_idが必要です'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, name, chapter_number, description
                    FROM input_units 
                    WHERE textbook_id = ?
                    ORDER BY chapter_number, name
                ''', (textbook_id,))
                
                units = []
                for row in cur.fetchall():
                    units.append({
                        'id': row[0],
                        'name': row[1],
                        'chapter_number': row[2],
                        'description': row[3]
                    })
                
                return jsonify(units)
                
    except Exception as e:
        app.logger.error(f"単元一覧取得APIエラー: {e}")
        return jsonify({'error': '単元一覧の取得に失敗しました'}), 500

@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    else:
        # 管理者の場合は管理画面、通常ユーザーの場合は生徒用ダッシュボード
        if current_user.is_admin:
            return redirect(url_for('admin.admin'))
        else:
            return render_template('index.html')

# ========== データベース初期化 ==========
def init_database():
    """データベースの初期化とテーブル作成"""
    db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type == 'sqlite':
        db_path = os.getenv('DB_PATH', 'flashcards.db')
        print(f"🔍 データベース設定: type=sqlite, path={db_path}")
        
        # データベースファイルの存在確認
        if os.path.exists(db_path):
            print("✅ SQLiteデータベースは既に存在します")
            
            # 既存のデータを確認
            try:
                with get_db_connection() as conn:
                    with get_db_cursor(conn) as cur:
                        cur.execute('SELECT COUNT(*) FROM users')
                        user_count = cur.fetchone()[0]
                        print(f"👥 既存のユーザー数: {user_count}")
                        
                        if user_count > 1:
                            print("⚠️  既存のユーザーデータが存在します - データを保持します")
            except Exception as e:
                print(f"⚠️  データベース確認エラー: {e}")
        else:
            print("📝 SQLiteデータベースを作成します")
        
        # データベース接続とテーブル作成
        try:
            with get_db_connection() as conn:
                with get_db_cursor(conn) as cur:
                    # テーブル作成（CREATE TABLE IF NOT EXISTSなので既存データは保持される）
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            full_name TEXT,
                            email TEXT,
                            password_hash TEXT NOT NULL,
                            is_admin BOOLEAN DEFAULT FALSE,
                            is_active BOOLEAN DEFAULT TRUE,
                            grade TEXT DEFAULT '一般',
                            last_login TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # その他のテーブルも作成
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS input_textbooks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            description TEXT,
                            question_types TEXT DEFAULT '["input"]',
                            subject TEXT DEFAULT '地理',
                            grade TEXT DEFAULT '高校',
                            publisher TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS input_units (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            textbook_id INTEGER,
                            title TEXT NOT NULL,
                            description TEXT,
                            unit_number INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (textbook_id) REFERENCES input_textbooks (id)
                        )
                    ''')
                    
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS input_questions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            unit_id INTEGER,
                            question_text TEXT NOT NULL,
                            correct_answer TEXT NOT NULL,
                            explanation TEXT,
                            image_path TEXT,
                            question_type TEXT DEFAULT 'input',
                            question_data TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (unit_id) REFERENCES input_units (id)
                        )
                    ''')
                    
                    conn.commit()
                    print("✅ テーブル作成完了")
                    
        except Exception as e:
            print(f"❌ データベース初期化エラー: {e}")
            return False
        
        return True
    else:
        # PostgreSQLの場合
        print(f"🔍 データベース設定: type=postgresql")
        try:
            # アプリケーションコンテキスト内で実行
            with app.app_context():
                with get_db_connection() as conn:
                    with get_db_cursor(conn) as cur:
                        # PostgreSQL用のテーブル作成
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS users (
                                id SERIAL PRIMARY KEY,
                                username VARCHAR(255) UNIQUE NOT NULL,
                                full_name VARCHAR(255),
                                email VARCHAR(255),
                                password_hash TEXT NOT NULL,
                                is_admin BOOLEAN DEFAULT FALSE,
                                is_active BOOLEAN DEFAULT TRUE,
                                grade VARCHAR(50) DEFAULT '一般',
                                last_login TIMESTAMP,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 学習ログテーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS study_log (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                card_id INTEGER NOT NULL,
                                source TEXT NOT NULL,
                                stage INTEGER NOT NULL,
                                mode TEXT NOT NULL,
                                result TEXT NOT NULL,
                                page_range TEXT,
                                difficulty TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # チャンク進捗テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS chunk_progress (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                source TEXT NOT NULL,
                                stage INTEGER NOT NULL,
                                page_range TEXT NOT NULL,
                                difficulty TEXT NOT NULL,
                                chunk_number INTEGER NOT NULL,
                                is_completed BOOLEAN DEFAULT FALSE,
                                is_passed BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 画像テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS image (
                                id SERIAL PRIMARY KEY,
                                source TEXT NOT NULL,
                                page_number INTEGER NOT NULL,
                                level TEXT,
                                image_path TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # ユーザー設定テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS user_settings (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                source TEXT NOT NULL,
                                page_range TEXT,
                                difficulty TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 入力問題テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS input_textbooks (
                                id SERIAL PRIMARY KEY,
                                name TEXT NOT NULL,
                                subject TEXT NOT NULL,
                                grade TEXT,
                                publisher TEXT,
                                description TEXT,
                                wasabi_folder_path TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS input_units (
                                id SERIAL PRIMARY KEY,
                                textbook_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                chapter_number INTEGER,
                                description TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS input_questions (
                                id SERIAL PRIMARY KEY,
                                subject TEXT NOT NULL,
                                textbook_id INTEGER NOT NULL,
                                unit_id INTEGER,
                                question TEXT NOT NULL,
                                correct_answer TEXT NOT NULL,
                                acceptable_answers TEXT,
                                answer_suffix TEXT,
                                explanation TEXT,
                                difficulty_level TEXT,
                                image_name TEXT,
                                image_url TEXT,
                                image_title TEXT,
                                question_number INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 入力問題学習ログテーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS input_study_log (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                question_id INTEGER NOT NULL,
                                user_answer TEXT,
                                is_correct BOOLEAN,
                                subject TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 選択問題テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS choice_textbooks (
                                id SERIAL PRIMARY KEY,
                                source TEXT NOT NULL,
                                chapter_name TEXT NOT NULL,
                                chapter_number INTEGER NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS choice_units (
                                id SERIAL PRIMARY KEY,
                                textbook_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                unit_number INTEGER NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS choice_questions (
                                id SERIAL PRIMARY KEY,
                                unit_id INTEGER NOT NULL,
                                question TEXT NOT NULL,
                                correct_answer TEXT NOT NULL,
                                choices TEXT NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS choice_study_log (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                question_id INTEGER NOT NULL,
                                user_answer TEXT,
                                correct_answer TEXT,
                                is_correct BOOLEAN NOT NULL,
                                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 統一された教材テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS textbooks (
                                id SERIAL PRIMARY KEY,
                                name TEXT NOT NULL,
                                subject TEXT NOT NULL,
                                grade TEXT,
                                publisher TEXT,
                                description TEXT,
                                study_type TEXT DEFAULT 'both',
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS units (
                                id SERIAL PRIMARY KEY,
                                textbook_id INTEGER NOT NULL,
                                name TEXT NOT NULL,
                                unit_number INTEGER NOT NULL,
                                description TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS questions (
                                id SERIAL PRIMARY KEY,
                                unit_id INTEGER NOT NULL,
                                question TEXT NOT NULL,
                                correct_answer TEXT NOT NULL,
                                choices TEXT,
                                acceptable_answers TEXT,
                                answer_suffix TEXT,
                                explanation TEXT,
                                difficulty_level TEXT,
                                image_name TEXT,
                                image_url TEXT,
                                image_title TEXT,
                                question_number INTEGER,
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 学習セッションテーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS study_sessions (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                textbook_id INTEGER NOT NULL,
                                unit_id INTEGER,
                                study_type TEXT NOT NULL,
                                progress REAL DEFAULT 0.0,
                                completed BOOLEAN DEFAULT FALSE,
                                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                completed_at TIMESTAMP,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 統一された学習ログテーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS study_logs (
                                id SERIAL PRIMARY KEY,
                                session_id INTEGER NOT NULL,
                                question_id INTEGER NOT NULL,
                                user_answer TEXT,
                                correct_answer TEXT,
                                is_correct BOOLEAN NOT NULL,
                                study_type TEXT NOT NULL,
                                response_time INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        # 教材割り当てテーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS textbook_assignments (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                textbook_id INTEGER NOT NULL,
                                study_type TEXT DEFAULT 'both',
                                units TEXT,
                                chunks TEXT,
                                is_active BOOLEAN DEFAULT TRUE,
                                assigned_by INTEGER NOT NULL,
                                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                expires_at TIMESTAMP
                            )
                        ''')
                        
                        # 教材割り当て詳細テーブル
                        cur.execute('''
                            CREATE TABLE IF NOT EXISTS assignment_details (
                                id SERIAL PRIMARY KEY,
                                assignment_id INTEGER NOT NULL,
                                unit_id INTEGER,
                                chunk_start INTEGER,
                                chunk_end INTEGER,
                                difficulty_level TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        
                        conn.commit()
                        print("✅ PostgreSQLテーブル作成完了")
                        
                        # インデックス作成
                        indexes = [
                            "CREATE INDEX IF NOT EXISTS idx_study_log_user_stage_mode ON study_log(user_id, stage, mode);",
                            "CREATE INDEX IF NOT EXISTS idx_study_log_composite ON study_log(user_id, stage, mode, card_id, id DESC);",
                            "CREATE INDEX IF NOT EXISTS idx_image_source_page ON image(source, page_number);",
                            "CREATE INDEX IF NOT EXISTS idx_image_source_level ON image(source, level);",
                            "CREATE INDEX IF NOT EXISTS idx_chunk_progress_user_source_stage ON chunk_progress(user_id, source, stage);",
                            "CREATE INDEX IF NOT EXISTS idx_study_log_card_result ON study_log(card_id, result, id DESC);",
                            "CREATE INDEX IF NOT EXISTS idx_user_settings_user_source ON user_settings(user_id, source);",
                            "CREATE INDEX IF NOT EXISTS idx_questions_textbook_unit ON input_questions(textbook_id, unit_id);",
                            "CREATE INDEX IF NOT EXISTS idx_choice_units_textbook ON choice_units(textbook_id, unit_number);",
                            "CREATE INDEX IF NOT EXISTS idx_choice_questions_unit ON choice_questions(unit_id);",
                            "CREATE INDEX IF NOT EXISTS idx_choice_study_log_user_question ON choice_study_log(user_id, question_id);",
                            "CREATE INDEX IF NOT EXISTS idx_choice_study_log_user ON choice_study_log(user_id, answered_at);"
                        ]
                        
                        for index_sql in indexes:
                            cur.execute(index_sql)
                        
                        print("✅ PostgreSQLインデックス作成完了")
                        
                        # デフォルト管理者ユーザーを作成（パスワード: admin123）
                        from werkzeug.security import generate_password_hash
                        
                        admin_password_hash = generate_password_hash('admin123')
                        cur.execute('''
                            INSERT INTO users (username, email, password_hash, is_admin, is_active)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (username) DO NOTHING
                        ''', ('admin', 'admin@example.com', admin_password_hash, True, True))
                        
                        conn.commit()
                        print("✅ PostgreSQL管理者ユーザー作成完了")
                        print("   ユーザー名: admin")
                        print("   パスワード: admin123")
                    
        except Exception as e:
            print(f"❌ PostgreSQL初期化エラー: {e}")
            return False
        
        return True

if __name__ == '__main__':
    # データベース初期化
    if not init_database():
        print("❌ データベース初期化に失敗しました")
        exit(1)
    
    # PostgreSQLの場合、データ移行を実行
    if os.getenv('DB_TYPE') == 'postgresql':
        try:
            print("🔄 PostgreSQLデータベースへの移行を確認しています...")
            from migrate_to_postgresql import migrate_to_postgresql
            migrate_to_postgresql()
        except Exception as e:
            print(f"❌ データ移行エラー: {e}")
    
    # 初期データの復元
    try:
        print("🔄 初期データの復元を確認しています...")
        from restore_data import restore_initial_data
        restore_initial_data()
    except Exception as e:
        print(f"❌ 初期データ復元エラー: {e}")
    
    # アプリケーションを起動
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 アプリケーションを起動します: port={port}")
    app.run(debug=False, host='0.0.0.0', port=port)