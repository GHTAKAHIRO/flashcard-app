# ========== Redis除去版 パート1: 基本設定・インポート・初期化 ==========
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
import math
# PostgreSQL関連のインポートをコメントアウト（SQLite使用時）
# import psycopg2
# from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from functools import wraps
import json
import hashlib
import threading
import time
import queue
# import psycopg2.pool
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
from routes.vocabulary import vocabulary_bp
from models.user import User
from utils.db import get_db_connection, get_db_cursor

# ========== 設定エリア ==========
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
logging.basicConfig(level=logging.DEBUG)

app.config.update(
    # JSON処理高速化
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=False,
    
    # セッション最適化
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    
    # 静的ファイルキャッシュ
    SEND_FILE_MAX_AGE_DEFAULT=31536000,  # 1年
    
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
app.register_blueprint(vocabulary_bp)

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
                    FROM social_studies_questions q
                    JOIN social_studies_units u ON q.unit_id = u.id
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
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
                    FROM social_studies_units u
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
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

@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    else:
        return redirect(url_for('admin.admin'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)