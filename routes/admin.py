from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from utils.db import get_db_connection, get_db_cursor
import csv
import io

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
def admin():
    """管理画面のメインページ"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) FROM users')
                user_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM study_log')
                study_log_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM social_studies_questions')
                question_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM vocabulary_words')
                vocabulary_count = cur.fetchone()[0]
                
                stats = {
                    'users': user_count,
                    'study_logs': study_log_count,
                    'questions': question_count,
                    'vocabulary_words': vocabulary_count
                }
                
                return render_template('admin.html', stats=stats)
                
    except Exception as e:
        current_app.logger.error(f"管理画面エラー: {e}")
        flash('管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('home'))

@admin_bp.route('/admin/users')
@login_required
def admin_users():
    """ユーザー管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 実際のデータベースからユーザーを取得
                cur.execute('''
                    SELECT id, username, email, is_admin, full_name, created_at, last_login
                    FROM users 
                    ORDER BY created_at DESC
                ''')
                users_data = cur.fetchall()
                
                users = []
                for user_data in users_data:
                    users.append({
                        'id': user_data[0],
                        'username': user_data[1],
                        'email': user_data[2],
                        'role': 'admin' if user_data[3] else 'user',
                        'full_name': user_data[4],
                        'created_at': user_data[5],
                        'last_login': user_data[6]
                    })
                
                return render_template('admin_users.html', users=users)
                
    except Exception as e:
        current_app.logger.error(f"ユーザー管理画面エラー: {e}")
        flash('ユーザー管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin'))

@admin_bp.route('/admin/users/add', methods=['POST'])
@login_required
def admin_add_user():
    """ユーザー追加"""
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if not all([username, email, password]):
        flash('すべてのフィールドを入力してください', 'error')
        return redirect(url_for('admin.admin_users'))
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザーが既に存在するかチェック
                cur.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
                if cur.fetchone():
                    flash('ユーザー名またはメールアドレスが既に使用されています', 'error')
                    return redirect(url_for('admin.admin_users'))
                
                # 新しいユーザーを追加
                from werkzeug.security import generate_password_hash
                hashed_password = generate_password_hash(password)
                is_admin = (role == 'admin')
                
                cur.execute('''
                    INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                ''', (username, email, hashed_password, is_admin, username))
                
                conn.commit()
                flash('ユーザーが正常に追加されました', 'success')
                
    except Exception as e:
        current_app.logger.error(f"ユーザー追加エラー: {e}")
        flash('ユーザーの追加に失敗しました', 'error')
    
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/users/upload_csv', methods=['POST'])
@login_required
def admin_upload_users_csv():
    """CSVファイルからユーザーを一括追加"""
    if 'csv_file' not in request.files:
        flash('CSVファイルが選択されていません', 'error')
        return redirect(url_for('admin.admin_users'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('ファイルが選択されていません', 'error')
        return redirect(url_for('admin.admin_users'))
    
    if not file.filename.endswith('.csv'):
        flash('CSVファイルを選択してください', 'error')
        return redirect(url_for('admin.admin_users'))
    
    try:
        # CSVファイルを読み込み
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                for row in csv_reader:
                    try:
                        username = row.get('username', '').strip()
                        email = row.get('email', '').strip()
                        password = row.get('password', '').strip()
                        role = row.get('role', 'user').strip()
                        full_name = row.get('full_name', username).strip()
                        
                        if not all([username, email, password]):
                            error_count += 1
                            continue
                        
                        # 重複チェック
                        cur.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
                        if cur.fetchone():
                            error_count += 1
                            continue
                        
                        # ユーザー追加
                        from werkzeug.security import generate_password_hash
                        hashed_password = generate_password_hash(password)
                        is_admin = (role == 'admin')
                        
                        cur.execute('''
                            INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
                            VALUES (?, ?, ?, ?, ?, datetime('now'))
                        ''', (username, email, hashed_password, is_admin, full_name))
                        
                        success_count += 1
                        
                    except Exception as e:
                        current_app.logger.error(f"CSV行処理エラー: {e}")
                        error_count += 1
                
                conn.commit()
        
        if success_count > 0:
            flash(f'{success_count}人のユーザーが正常に追加されました', 'success')
        if error_count > 0:
            flash(f'{error_count}件のエラーが発生しました', 'warning')
            
    except Exception as e:
        current_app.logger.error(f"CSVアップロードエラー: {e}")
        flash('CSVファイルの処理に失敗しました', 'error')
    
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/users/csv_template')
@login_required
def admin_users_csv_template():
    """ユーザーCSVテンプレートのダウンロード"""
    from flask import send_file
    
    # CSVテンプレートを作成
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['username', 'email', 'password', 'role', 'full_name'])
    writer.writerow(['user1', 'user1@example.com', 'password123', 'user', 'User One'])
    writer.writerow(['user2', 'user2@example.com', 'password456', 'user', 'User Two'])
    
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='users_template.csv'
    )

@admin_bp.route('/admin/users/<int:user_id>')
@login_required
def admin_get_user(user_id):
    """ユーザー情報の取得（編集用）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, username, email, is_admin, full_name
                    FROM users 
                    WHERE id = ?
                ''', (user_id,))
                user_data = cur.fetchone()
                
                if not user_data:
                    return jsonify({'error': 'ユーザーが見つかりません'}), 404
                
                user = {
                    'id': user_data[0],
                    'username': user_data[1],
                    'email': user_data[2],
                    'is_admin': bool(user_data[3]),
                    'full_name': user_data[4]
                }
                
                return jsonify(user)
                
    except Exception as e:
        current_app.logger.error(f"ユーザー取得エラー: {e}")
        return jsonify({'error': 'ユーザー情報の取得に失敗しました'}), 500

@admin_bp.route('/admin/users/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user(user_id):
    """ユーザー情報の更新"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        is_admin = data.get('is_admin', False)
        
        if not username:
            return jsonify({'error': 'ユーザー名は必須です'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザーが存在するかチェック
                cur.execute('SELECT id FROM users WHERE id = ?', (user_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'ユーザーが見つかりません'}), 404
                
                # ユーザー名とメールの重複チェック（自分以外）
                cur.execute('SELECT id FROM users WHERE (username = ? OR email = ?) AND id != ?', 
                           (username, email, user_id))
                if cur.fetchone():
                    return jsonify({'error': 'ユーザー名またはメールアドレスが既に使用されています'}), 400
                
                # 更新処理
                if password:
                    # パスワードも更新
                    from werkzeug.security import generate_password_hash
                    hashed_password = generate_password_hash(password)
                    cur.execute('''
                        UPDATE users 
                        SET username = ?, email = ?, password_hash = ?, is_admin = ?
                        WHERE id = ?
                    ''', (username, email, hashed_password, is_admin, user_id))
                else:
                    # パスワードは更新しない
                    cur.execute('''
                        UPDATE users 
                        SET username = ?, email = ?, is_admin = ?
                        WHERE id = ?
                    ''', (username, email, is_admin, user_id))
                
                conn.commit()
                return jsonify({'message': 'ユーザーを更新しました'})
                
    except Exception as e:
        current_app.logger.error(f"ユーザー更新エラー: {e}")
        return jsonify({'error': 'ユーザーの更新に失敗しました'}), 500

@admin_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    """ユーザーの削除"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザーが存在するかチェック
                cur.execute('SELECT id FROM users WHERE id = ?', (user_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'ユーザーが見つかりません'}), 404
                
                # 自分自身は削除できない
                if user_id == current_user.id:
                    return jsonify({'error': '自分自身を削除することはできません'}), 400
                
                # ユーザーを削除
                cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                
                return jsonify({'message': 'ユーザーを削除しました'})
                
    except Exception as e:
        current_app.logger.error(f"ユーザー削除エラー: {e}")
        return jsonify({'error': 'ユーザーの削除に失敗しました'}), 500 