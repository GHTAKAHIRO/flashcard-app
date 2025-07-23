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
                
                return render_template('admin.html', 
                                     total_users=user_count,
                                     total_study_logs=study_log_count,
                                     total_questions=question_count,
                                     total_vocabulary_words=vocabulary_count)
                
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

@admin_bp.route('/admin/social_studies/questions')
@login_required
def social_studies_admin_questions():
    """社会科問題一覧管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題一覧を取得
                cur.execute('''
                    SELECT q.id, q.question_text, q.answer_text, q.explanation, 
                           q.subject, q.difficulty, q.created_at,
                           t.name as textbook_name, u.name as unit_name
                    FROM social_studies_questions q
                    LEFT JOIN social_studies_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN social_studies_units u ON q.unit_id = u.id
                    ORDER BY q.created_at DESC
                ''')
                questions_data = cur.fetchall()
                
                questions = []
                for q_data in questions_data:
                    questions.append({
                        'id': q_data[0],
                        'question_text': q_data[1],
                        'answer_text': q_data[2],
                        'explanation': q_data[3],
                        'subject': q_data[4],
                        'difficulty': q_data[5],
                        'created_at': q_data[6],
                        'textbook_name': q_data[7] or '未設定',
                        'unit_name': q_data[8] or '未設定'
                    })
                
                return render_template('social_studies/admin_questions.html', questions=questions)
                
    except Exception as e:
        current_app.logger.error(f"社会科問題管理画面エラー: {e}")
        flash('社会科問題管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin'))

@admin_bp.route('/admin/social_studies/questions/add')
@login_required
def social_studies_add_question():
    """社会科問題追加画面"""
    try:
        textbook_id = request.args.get('textbook_id', type=int)
        unit_id = request.args.get('unit_id', type=int)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                if textbook_id and unit_id:
                    # 特定の教材・単元の問題を追加する場合
                    cur.execute('''
                        SELECT t.id, t.name, t.subject, u.id, u.name
                        FROM social_studies_textbooks t
                        JOIN social_studies_units u ON t.id = u.textbook_id
                        WHERE t.id = ? AND u.id = ?
                    ''', (textbook_id, unit_id))
                    data = cur.fetchone()
                    
                    if not data:
                        flash('教材または単元が見つかりません', 'error')
                        return redirect(url_for('admin.social_studies_admin_unified'))
                    
                    textbook_info = {
                        'id': data[0],
                        'name': data[1],
                        'subject': data[2]
                    }
                    
                    unit_info = {
                        'id': data[3],
                        'name': data[4]
                    }
                    
                    return render_template('social_studies/add_question.html', 
                                         textbook_info=textbook_info, unit_info=unit_info)
                else:
                    # 教材一覧を取得
                    cur.execute('SELECT id, name, subject FROM social_studies_textbooks ORDER BY subject, name')
                    textbooks = cur.fetchall()
                    
                    # 単元一覧を取得
                    cur.execute('SELECT id, name, textbook_id FROM social_studies_units ORDER BY textbook_id, name')
                    units = cur.fetchall()
                    
                    return render_template('social_studies/add_question.html', 
                                         textbooks=textbooks, units=units)
                
    except Exception as e:
        current_app.logger.error(f"社会科問題追加画面エラー: {e}")
        flash('社会科問題追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.social_studies_admin_questions'))

@admin_bp.route('/admin/social_studies/questions/add', methods=['POST'])
@login_required
def social_studies_add_question_post():
    """社会科問題追加処理"""
    try:
        question_text = request.form.get('question_text', '').strip()
        answer_text = request.form.get('answer_text', '').strip()
        explanation = request.form.get('explanation', '').strip()
        subject = request.form.get('subject', '').strip()
        difficulty = request.form.get('difficulty', 'normal')
        textbook_id = request.form.get('textbook_id', type=int)
        unit_id = request.form.get('unit_id', type=int)
        
        # バリデーション
        if not question_text:
            flash('問題文は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_question'))
        
        if not answer_text:
            flash('正解は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_question'))
        
        if not subject:
            flash('科目は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_question'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材と単元の存在チェック
                if textbook_id:
                    cur.execute('SELECT id FROM social_studies_textbooks WHERE id = ?', (textbook_id,))
                    if not cur.fetchone():
                        flash('指定された教材が見つかりません', 'error')
                        return redirect(url_for('admin.social_studies_add_question'))
                
                if unit_id:
                    cur.execute('SELECT id FROM social_studies_units WHERE id = ?', (unit_id,))
                    if not cur.fetchone():
                        flash('指定された単元が見つかりません', 'error')
                        return redirect(url_for('admin.social_studies_add_question'))
                
                # 問題を追加
                cur.execute('''
                    INSERT INTO social_studies_questions 
                    (question_text, answer_text, explanation, subject, difficulty, textbook_id, unit_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (question_text, answer_text, explanation, subject, difficulty, textbook_id, unit_id))
                
                conn.commit()
                flash('問題を追加しました', 'success')
                
                # リダイレクト先を決定
                if unit_id:
                    return redirect(url_for('admin.social_studies_admin_unit_questions', unit_id=unit_id))
                elif textbook_id:
                    return redirect(url_for('admin.social_studies_admin_textbook_unified', textbook_id=textbook_id))
                else:
                    return redirect(url_for('admin.social_studies_admin_questions'))
                
    except Exception as e:
        current_app.logger.error(f"社会科問題追加エラー: {e}")
        flash('問題の追加に失敗しました', 'error')
        return redirect(url_for('admin.social_studies_add_question'))

@admin_bp.route('/admin/social_studies/unified')
@login_required
def social_studies_admin_unified():
    """社会科統合管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) FROM social_studies_questions')
                question_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM social_studies_textbooks')
                textbook_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM social_studies_units')
                unit_count = cur.fetchone()[0]
                
                # 教材一覧を取得
                cur.execute('''
                    SELECT t.id, t.name, t.subject, t.grade, t.publisher, t.description,
                           COUNT(DISTINCT u.id) as unit_count,
                           COUNT(DISTINCT q.id) as question_count
                    FROM social_studies_textbooks t
                    LEFT JOIN social_studies_units u ON t.id = u.textbook_id
                    LEFT JOIN social_studies_questions q ON t.id = q.textbook_id
                    GROUP BY t.id
                    ORDER BY t.subject, t.name
                ''')
                textbooks_data = cur.fetchall()
                
                textbooks = []
                for t_data in textbooks_data:
                    textbooks.append({
                        'id': t_data[0],
                        'name': t_data[1],
                        'subject': t_data[2],
                        'grade': t_data[3],
                        'publisher': t_data[4],
                        'description': t_data[5],
                        'unit_count': t_data[6],
                        'question_count': t_data[7]
                    })
                
                return render_template('social_studies/admin_unified.html', 
                                     stats={'questions': question_count, 'textbooks': textbook_count, 'units': unit_count},
                                     textbooks=textbooks)
                
    except Exception as e:
        current_app.logger.error(f"社会科統合管理画面エラー: {e}")
        flash('社会科統合管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin')) 

@admin_bp.route('/admin/social_studies/textbooks/add')
@login_required
def social_studies_add_textbook():
    """社会科教材追加画面"""
    try:
        return render_template('social_studies/add_textbook.html')
    except Exception as e:
        current_app.logger.error(f"社会科教材追加画面エラー: {e}")
        flash('社会科教材追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.social_studies_admin_unified'))

@admin_bp.route('/admin/social_studies/textbooks/add', methods=['POST'])
@login_required
def social_studies_add_textbook_post():
    """社会科教材追加処理"""
    try:
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        grade = request.form.get('grade', '').strip()
        publisher = request.form.get('publisher', '').strip()
        description = request.form.get('description', '').strip()
        
        # バリデーション
        if not name:
            flash('教材名は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_textbook'))
        
        if not subject:
            flash('科目は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_textbook'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材名の重複チェック
                cur.execute('SELECT id FROM social_studies_textbooks WHERE name = ?', (name,))
                if cur.fetchone():
                    flash('この教材名は既に使用されています', 'error')
                    return redirect(url_for('admin.social_studies_add_textbook'))
                
                # 教材を追加
                cur.execute('''
                    INSERT INTO social_studies_textbooks (name, subject, grade, publisher, description, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                ''', (name, subject, grade, publisher, description))
                
                conn.commit()
                flash('教材を追加しました', 'success')
                return redirect(url_for('admin.social_studies_admin_unified'))
                
    except Exception as e:
        current_app.logger.error(f"社会科教材追加エラー: {e}")
        flash('教材の追加に失敗しました', 'error')
        return redirect(url_for('admin.social_studies_add_textbook'))

@admin_bp.route('/admin/social_studies/textbooks/<int:textbook_id>')
@login_required
def social_studies_admin_textbook_unified(textbook_id):
    """社会科教材詳細管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材情報を取得
                cur.execute('''
                    SELECT id, name, subject, grade, publisher, description, created_at
                    FROM social_studies_textbooks 
                    WHERE id = ?
                ''', (textbook_id,))
                textbook_data = cur.fetchone()
                
                if not textbook_data:
                    flash('教材が見つかりません', 'error')
                    return redirect(url_for('admin.social_studies_admin_unified'))
                
                textbook_info = {
                    'id': textbook_data[0],
                    'name': textbook_data[1],
                    'subject': textbook_data[2],
                    'grade': textbook_data[3],
                    'publisher': textbook_data[4],
                    'description': textbook_data[5],
                    'created_at': textbook_data[6]
                }
                
                # 単元一覧を取得
                cur.execute('''
                    SELECT id, name, description, created_at
                    FROM social_studies_units 
                    WHERE textbook_id = ?
                    ORDER BY name
                ''', (textbook_id,))
                units_data = cur.fetchall()
                
                units = []
                for unit_data in units_data:
                    units.append({
                        'id': unit_data[0],
                        'name': unit_data[1],
                        'description': unit_data[2],
                        'created_at': unit_data[3]
                    })
                
                # 問題数を取得
                cur.execute('SELECT COUNT(*) FROM social_studies_questions WHERE textbook_id = ?', (textbook_id,))
                question_count = cur.fetchone()[0]
                
                return render_template('social_studies/admin_textbook_unified.html', 
                                     textbook_info=textbook_info, 
                                     units=units,
                                     question_count=question_count)
                
    except Exception as e:
        current_app.logger.error(f"社会科教材詳細管理画面エラー: {e}")
        flash('社会科教材詳細管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.social_studies_admin_unified'))

@admin_bp.route('/admin/social_studies/units/add')
@login_required
def social_studies_add_unit():
    """社会科単元追加画面"""
    try:
        textbook_id = request.args.get('textbook_id', type=int)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                if textbook_id:
                    # 特定の教材の単元を追加する場合
                    cur.execute('SELECT id, name, subject FROM social_studies_textbooks WHERE id = ?', (textbook_id,))
                    textbook_data = cur.fetchone()
                    
                    if not textbook_data:
                        flash('教材が見つかりません', 'error')
                        return redirect(url_for('admin.social_studies_admin_unified'))
                    
                    textbook = {
                        'id': textbook_data[0],
                        'name': textbook_data[1],
                        'subject': textbook_data[2]
                    }
                    
                    return render_template('social_studies/add_unit.html', textbook=textbook)
                else:
                    # 教材一覧を取得
                    cur.execute('SELECT id, name, subject FROM social_studies_textbooks ORDER BY subject, name')
                    textbooks = cur.fetchall()
                    
                    return render_template('social_studies/add_unit.html', textbooks=textbooks)
                
    except Exception as e:
        current_app.logger.error(f"社会科単元追加画面エラー: {e}")
        flash('社会科単元追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.social_studies_admin_unified'))

@admin_bp.route('/admin/social_studies/units/add', methods=['POST'])
@login_required
def social_studies_add_unit_post():
    """社会科単元追加処理"""
    try:
        name = request.form.get('name', '').strip()
        chapter_number = request.form.get('chapter_number', '').strip()
        description = request.form.get('description', '').strip()
        textbook_id = request.args.get('textbook_id', type=int)
        
        # バリデーション
        if not name:
            flash('単元名は必須です', 'error')
            return redirect(url_for('admin.social_studies_add_unit', textbook_id=textbook_id))
        
        if not textbook_id:
            flash('教材IDが指定されていません', 'error')
            return redirect(url_for('admin.social_studies_admin_unified'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材が存在するかチェック
                cur.execute('SELECT id FROM social_studies_textbooks WHERE id = ?', (textbook_id,))
                if not cur.fetchone():
                    flash('指定された教材が見つかりません', 'error')
                    return redirect(url_for('admin.social_studies_admin_unified'))
                
                # 単元名の重複チェック（同じ教材内で）
                cur.execute('SELECT id FROM social_studies_units WHERE name = ? AND textbook_id = ?', (name, textbook_id))
                if cur.fetchone():
                    flash('この単元名は既に使用されています', 'error')
                    return redirect(url_for('admin.social_studies_add_unit', textbook_id=textbook_id))
                
                # 章番号の処理
                chapter_num = None
                if chapter_number:
                    try:
                        chapter_num = int(chapter_number)
                    except ValueError:
                        flash('章番号は数値で入力してください', 'error')
                        return redirect(url_for('admin.social_studies_add_unit', textbook_id=textbook_id))
                
                # 単元を追加
                cur.execute('''
                    INSERT INTO social_studies_units (name, chapter_number, description, textbook_id, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                ''', (name, chapter_num, description, textbook_id))
                
                conn.commit()
                flash('単元を追加しました', 'success')
                return redirect(url_for('admin.social_studies_admin_textbook_unified', textbook_id=textbook_id))
                
    except Exception as e:
        current_app.logger.error(f"社会科単元追加エラー: {e}")
        flash('単元の追加に失敗しました', 'error')
        return redirect(url_for('admin.social_studies_add_unit', textbook_id=textbook_id))

@admin_bp.route('/admin/social_studies/units/<int:unit_id>/questions')
@login_required
def social_studies_admin_unit_questions(unit_id):
    """社会科単元問題管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元情報を取得
                cur.execute('''
                    SELECT u.id, u.name, u.description, t.id as textbook_id, t.name as textbook_name
                    FROM social_studies_units u
                    JOIN social_studies_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = ?
                ''', (unit_id,))
                unit_data = cur.fetchone()
                
                if not unit_data:
                    flash('単元が見つかりません', 'error')
                    return redirect(url_for('admin.social_studies_admin_unified'))
                
                textbook_info = {
                    'id': unit_data[3],
                    'name': unit_data[4]
                }
                
                unit_info = {
                    'id': unit_data[0],
                    'name': unit_data[1],
                    'description': unit_data[2]
                }
                
                # 問題一覧を取得
                cur.execute('''
                    SELECT id, question_text, answer_text, explanation, difficulty, created_at
                    FROM social_studies_questions 
                    WHERE unit_id = ?
                    ORDER BY created_at DESC
                ''', (unit_id,))
                questions_data = cur.fetchall()
                
                questions = []
                for q_data in questions_data:
                    questions.append({
                        'id': q_data[0],
                        'question_text': q_data[1],
                        'answer_text': q_data[2],
                        'explanation': q_data[3],
                        'difficulty': q_data[4],
                        'created_at': q_data[5]
                    })
                
                return render_template('social_studies/admin_unit_questions.html', 
                                     textbook_info=textbook_info,
                                     unit_info=unit_info,
                                     questions=questions)
                
    except Exception as e:
        current_app.logger.error(f"社会科単元問題管理画面エラー: {e}")
        flash('社会科単元問題管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.social_studies_admin_unified')) 