from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from utils.db import get_db_connection, get_db_cursor, get_placeholder
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
                
                cur.execute('SELECT COUNT(*) FROM input_questions')
                question_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM choice_units')
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

@admin_bp.route('/admin/restore_data', methods=['POST'])
@login_required
def restore_data():
    """初期データの復元"""
    try:
        from restore_data import restore_initial_data
        restore_initial_data()
        flash('初期データの復元が完了しました', 'success')
    except Exception as e:
        current_app.logger.error(f"データ復元エラー: {e}")
        flash('データ復元に失敗しました', 'error')
    
    return redirect(url_for('admin.admin'))

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
    full_name = request.form.get('full_name')
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if not all([full_name, username, password]):
        flash('すべてのフィールドを入力してください', 'error')
        return redirect(url_for('admin.admin_users'))
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザーが既に存在するかチェック
                placeholder = get_placeholder()
                cur.execute(f'SELECT id FROM users WHERE username = {placeholder}', (username,))
                if cur.fetchone():
                    flash('ログインIDが既に使用されています', 'error')
                    return redirect(url_for('admin.admin_users'))
                
                # 新しいユーザーを追加
                from werkzeug.security import generate_password_hash
                hashed_password = generate_password_hash(password)
                is_admin = (role == 'admin')
                
                cur.execute(f'''
                    INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
                    VALUES ({placeholder}, NULL, {placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
                ''', (username, hashed_password, is_admin, full_name))
                
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
        # CSVファイルを読み込み（BOM対応）
        content = file.read()
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]  # BOMを除去
        content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        success_count = 0
        error_count = 0
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                for row in csv_reader:
                    try:
                        # 新しいヘッダー構造に対応
                        full_name = row.get('表示名（氏名）', row.get('full_name', '')).strip()
                        username = row.get('ログインID', row.get('username', '')).strip()
                        password = row.get('パスワード', row.get('password', '')).strip()
                        role = row.get('役割', row.get('role', 'user')).strip()
                        
                        if not all([full_name, username, password]):
                            error_count += 1
                            continue
                        
                        # 重複チェック
                        placeholder = get_placeholder()
                        cur.execute(f'SELECT id FROM users WHERE username = {placeholder}', (username,))
                        if cur.fetchone():
                            error_count += 1
                            continue
                        
                        # ユーザー追加
                        from werkzeug.security import generate_password_hash
                        hashed_password = generate_password_hash(password)
                        # 権限の日本語対応
                        is_admin = (role.lower() in ['admin', '管理者'])
                        
                        cur.execute(f'''
                            INSERT INTO users (username, email, password_hash, is_admin, full_name, created_at)
                            VALUES ({placeholder}, NULL, {placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
                        ''', (username, hashed_password, is_admin, full_name))
                        
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
    
    # CSVテンプレートを作成（BOM付きUTF-8で文字化けを防ぐ）
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['表示名（氏名）', 'ログインID', 'パスワード', '役割'])
    writer.writerow(['田中太郎', 'tanaka001', 'So-12345', 'user'])
    writer.writerow(['佐藤花子', 'sato002', 'So-67890', 'user'])
    
    # BOM付きUTF-8でエンコード
    csv_content = output.getvalue()
    output_bytes = io.BytesIO()
    output_bytes.write(b'\xef\xbb\xbf')  # BOM
    output_bytes.write(csv_content.encode('utf-8'))
    output_bytes.seek(0)
    
    from flask import Response
    return Response(
        output_bytes.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': 'attachment; filename=users_template.csv',
            'Content-Type': 'text/csv; charset=utf-8'
        }
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
                placeholder = get_placeholder()
                cur.execute(f'SELECT id FROM users WHERE id = {placeholder}', (user_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'ユーザーが見つかりません'}), 404
                
                # ユーザー名とメールの重複チェック（自分以外）
                cur.execute(f'SELECT id FROM users WHERE (username = {placeholder} OR email = {placeholder}) AND id != {placeholder}', 
                           (username, email, user_id))
                if cur.fetchone():
                    return jsonify({'error': 'ユーザー名またはメールアドレスが既に使用されています'}), 400
                
                # 更新処理
                if password:
                    # パスワードも更新
                    from werkzeug.security import generate_password_hash
                    hashed_password = generate_password_hash(password)
                    cur.execute(f'''
                        UPDATE users 
                        SET username = {placeholder}, email = {placeholder}, password_hash = {placeholder}, is_admin = {placeholder}
                        WHERE id = {placeholder}
                    ''', (username, email, hashed_password, is_admin, user_id))
                else:
                    # パスワードは更新しない
                    cur.execute(f'''
                        UPDATE users 
                        SET username = {placeholder}, email = {placeholder}, is_admin = {placeholder}
                        WHERE id = {placeholder}
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
                placeholder = get_placeholder()
                cur.execute(f'SELECT id FROM users WHERE id = {placeholder}', (user_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'ユーザーが見つかりません'}), 404
                
                # 自分自身は削除できない
                if user_id == current_user.id:
                    return jsonify({'error': '自分自身を削除することはできません'}), 400
                
                # ユーザーを削除
                cur.execute(f'DELETE FROM users WHERE id = {placeholder}', (user_id,))
                conn.commit()
                
                return jsonify({'message': 'ユーザーを削除しました'})
                
    except Exception as e:
        current_app.logger.error(f"ユーザー削除エラー: {e}")
        return jsonify({'error': 'ユーザーの削除に失敗しました'}), 500 

@admin_bp.route('/admin/input_studies/questions')
@login_required
def input_studies_admin_questions():
    """社会科問題一覧管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題一覧を取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT q.id, q.question, q.correct_answer, q.explanation, 
                           q.subject, q.difficulty_level, q.created_at,
                           t.name as textbook_name, u.name as unit_name
                    FROM input_questions q
                    LEFT JOIN input_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN input_units u ON q.unit_id = u.id
                    ORDER BY q.created_at DESC
                ''')
                questions_data = cur.fetchall()
                
                questions = []
                for q_data in questions_data:
                    questions.append({
                        'id': q_data[0],
                        'question_text': q_data[1],  # questionカラムをquestion_textとして扱う
                        'answer_text': q_data[2],    # correct_answerカラムをanswer_textとして扱う
                        'explanation': q_data[3],
                        'subject': q_data[4],
                        'difficulty': q_data[5],     # difficulty_levelカラムをdifficultyとして扱う
                        'created_at': q_data[6],
                        'textbook_name': q_data[7] or '未設定',
                        'unit_name': q_data[8] or '未設定'
                    })
                
                return render_template('input_studies/admin_questions.html', questions=questions)
                
    except Exception as e:
        current_app.logger.error(f"社会科問題管理画面エラー: {e}")
        flash('社会科問題管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin'))

@admin_bp.route('/admin/input_studies/questions/add')
@login_required
def input_studies_add_question():
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
                        FROM input_textbooks t
                        JOIN input_units u ON t.id = u.textbook_id
                        WHERE t.id = ? AND u.id = ?
                    ''', (textbook_id, unit_id))
                    data = cur.fetchone()
                    
                    if not data:
                        flash('教材または単元が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_admin_unified'))
                    
                    textbook_info = {
                        'id': data[0],
                        'name': data[1],
                        'subject': data[2]
                    }
                    
                    unit_info = {
                        'id': data[3],
                        'name': data[4]
                    }
                    
                    return render_template('input_studies/add_question.html', 
                                         textbook_info=textbook_info, unit_info=unit_info,
                                         textbook_id=textbook_id, unit_id=unit_id)
                else:
                    # 教材一覧を取得
                    cur.execute('SELECT id, name, subject FROM input_textbooks ORDER BY subject, name')
                    textbooks = cur.fetchall()
                    
                    # 単元一覧を取得
                    cur.execute('SELECT id, name, textbook_id FROM input_units ORDER BY textbook_id, name')
                    units = cur.fetchall()
                    
                    return render_template('input_studies/add_question.html', 
                                         textbooks=textbooks, units=units,
                                         textbook_id=None, unit_id=None)
                
    except Exception as e:
        current_app.logger.error(f"社会科問題追加画面エラー: {e}")
        flash('社会科問題追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_questions'))

@admin_bp.route('/admin/input_studies/questions/add', methods=['POST'])
@login_required
def input_studies_add_question_post():
    """社会科問題追加処理"""
    try:
        question_text = request.form.get('question_text', '').strip()
        answer_text = request.form.get('answer_text', '').strip()
        explanation = request.form.get('explanation', '').strip()
        subject = request.form.get('subject', '').strip()
        difficulty = request.form.get('difficulty', 'normal')
        textbook_id = request.form.get('textbook_id', type=int)
        unit_id = request.form.get('unit_id', type=int)
        question_number = request.form.get('question_number', type=int)
        image_path = request.form.get('image_path', '').strip()
        
        # バリデーション
        if not question_text:
            flash('問題文は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_question'))
        
        if not answer_text:
            flash('正解は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_question'))
        
        if not subject:
            flash('科目は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_question'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材と単元の存在チェック
                placeholder = get_placeholder()
                if textbook_id:
                    cur.execute(f'SELECT id FROM input_textbooks WHERE id = {placeholder}', (textbook_id,))
                    if not cur.fetchone():
                        flash('指定された教材が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_add_question'))
                
                if unit_id:
                    cur.execute(f'SELECT id FROM input_units WHERE id = {placeholder}', (unit_id,))
                    if not cur.fetchone():
                        flash('指定された単元が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_add_question'))
                
                # 問題番号の自動割り当て
                if not question_number:
                    if unit_id:
                        # 単元が指定されている場合、その単元内での次の番号を取得
                        cur.execute(f'''
                            SELECT COALESCE(MAX(question_number), 0) + 1 
                            FROM input_questions 
                            WHERE unit_id = {placeholder}
                        ''', (unit_id,))
                        question_number = cur.fetchone()[0]
                    else:
                        # 単元が指定されていない場合、全体での次の番号を取得
                        cur.execute('SELECT COALESCE(MAX(question_number), 0) + 1 FROM input_questions')
                        question_number = cur.fetchone()[0]
                
                # 問題を追加
                cur.execute(f'''
                    INSERT INTO input_questions 
                    (question, correct_answer, explanation, subject, difficulty_level, textbook_id, unit_id, question_number, image_path, created_at)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
                ''', (question_text, answer_text, explanation, subject, difficulty, textbook_id, unit_id, question_number, image_path))
                
                conn.commit()
                flash('問題を追加しました', 'success')
                
                # リダイレクト先を決定
                if unit_id:
                    return redirect(url_for('admin.input_studies_admin_unit_questions', unit_id=unit_id))
                elif textbook_id:
                    return redirect(url_for('admin.input_studies_admin_textbook_unified', textbook_id=textbook_id))
                else:
                    return redirect(url_for('admin.input_studies_admin_questions'))
                
    except Exception as e:
        current_app.logger.error(f"社会科問題追加エラー: {e}")
        flash('問題の追加に失敗しました', 'error')
        return redirect(url_for('admin.input_studies_add_question'))

@admin_bp.route('/admin/input_studies/unified')
@login_required
def input_studies_admin_unified():
    """社会科統合管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 統計情報を取得
                cur.execute('SELECT COUNT(*) FROM input_questions')
                question_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM input_textbooks')
                textbook_count = cur.fetchone()[0]
                
                cur.execute('SELECT COUNT(*) FROM input_units')
                unit_count = cur.fetchone()[0]
                
                # 教材一覧を取得
                cur.execute('''
                    SELECT t.id, t.name, t.subject, t.grade, t.publisher, t.description,
                           COUNT(DISTINCT u.id) as unit_count,
                           COUNT(DISTINCT q.id) as question_count
                    FROM input_textbooks t
                    LEFT JOIN input_units u ON t.id = u.textbook_id
                    LEFT JOIN input_questions q ON t.id = q.textbook_id
                    GROUP BY t.id
                    ORDER BY t.subject, t.name
                ''')
                textbooks_data = cur.fetchall()
                
                current_app.logger.info(f"教材一覧取得: {len(textbooks_data)} 件")
                
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
                    current_app.logger.info(f"教材: ID={t_data[0]}, name={t_data[1]}, subject={t_data[2]}")
                
                return render_template('input_studies/admin_unified.html', 
                                     stats={'questions': question_count, 'textbooks': textbook_count, 'units': unit_count},
                                     textbooks=textbooks)
                
    except Exception as e:
        current_app.logger.error(f"社会科統合管理画面エラー: {e}")
        flash('社会科統合管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.admin')) 

@admin_bp.route('/admin/input_studies/textbooks/add')
@login_required
def input_studies_add_textbook():
    """社会科教材追加画面"""
    try:
        return render_template('input_studies/add_textbook.html')
    except Exception as e:
        current_app.logger.error(f"社会科教材追加画面エラー: {e}")
        flash('社会科教材追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_unified'))

@admin_bp.route('/admin/input_studies/textbooks/add', methods=['POST'])
@login_required
def input_studies_add_textbook_post():
    """社会科教材追加処理"""
    try:
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        grade = request.form.get('grade', '').strip()
        publisher = request.form.get('publisher', '').strip()
        description = request.form.get('description', '').strip()
        
        current_app.logger.info(f"教材追加開始: name={name}, subject={subject}")
        
        # バリデーション
        if not name:
            flash('教材名は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_textbook'))
        
        if not subject:
            flash('科目は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_textbook'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材名の重複チェック
                cur.execute('SELECT id FROM input_textbooks WHERE name = ?', (name,))
                if cur.fetchone():
                    flash('この教材名は既に使用されています', 'error')
                    return redirect(url_for('admin.input_studies_add_textbook'))
                
                # 教材を追加
                cur.execute('''
                    INSERT INTO input_textbooks (name, subject, grade, publisher, description, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                ''', (name, subject, grade, publisher, description))
                
                # 追加された教材のIDを取得
                textbook_id = cur.lastrowid
                current_app.logger.info(f"教材追加完了: ID={textbook_id}")
                
                conn.commit()
                current_app.logger.info(f"データベースコミット完了: ID={textbook_id}")
                
                # 追加された教材を確認
                cur.execute('SELECT id, name, subject FROM input_textbooks WHERE id = ?', (textbook_id,))
                added_textbook = cur.fetchone()
                if added_textbook:
                    current_app.logger.info(f"追加確認: ID={added_textbook[0]}, name={added_textbook[1]}")
                else:
                    current_app.logger.error(f"追加確認失敗: ID={textbook_id} が見つかりません")
                
                flash('教材を追加しました', 'success')
                return redirect(url_for('admin.input_studies_admin_unified'))
                
    except Exception as e:
        current_app.logger.error(f"社会科教材追加エラー: {e}")
        flash('教材の追加に失敗しました', 'error')
        return redirect(url_for('admin.input_studies_add_textbook'))

@admin_bp.route('/admin/input_studies/textbooks/<int:textbook_id>')
@login_required
def input_studies_admin_textbook_unified(textbook_id):
    """社会科教材詳細管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材情報を取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT id, name, subject, grade, publisher, description, created_at
                    FROM input_textbooks 
                    WHERE id = {placeholder}
                ''', (textbook_id,))
                textbook_data = cur.fetchone()
                
                if not textbook_data:
                    flash('教材が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_unified'))
                
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
                cur.execute(f'''
                    SELECT id, name, chapter_number, description, created_at
                    FROM input_units 
                    WHERE textbook_id = {placeholder}
                    ORDER BY chapter_number, name
                ''', (textbook_id,))
                units_data = cur.fetchall()
                
                units = []
                for unit_data in units_data:
                    units.append({
                        'id': unit_data[0],
                        'name': unit_data[1],
                        'chapter_number': unit_data[2],
                        'description': unit_data[3],
                        'created_at': unit_data[4]
                    })
                
                # 問題数を取得
                cur.execute(f'SELECT COUNT(*) FROM input_questions WHERE textbook_id = {placeholder}', (textbook_id,))
                question_count = cur.fetchone()[0]
                
                # 学習ログ数を取得
                cur.execute(f'''
                    SELECT COUNT(*) FROM input_study_log 
                    WHERE question_id IN (
                        SELECT id FROM input_questions WHERE textbook_id = {placeholder}
                    )
                ''', (textbook_id,))
                study_log_count = cur.fetchone()[0]
                
                return render_template('input_studies/admin_textbook_unified.html', 
                                     textbook=textbook_info, 
                                     units=units,
                                     total_units=len(units),
                                     total_questions=question_count,
                                     total_study_logs=study_log_count)
                
    except Exception as e:
        current_app.logger.error(f"社会科教材詳細管理画面エラー: {e}")
        flash('社会科教材詳細管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_unified'))

@admin_bp.route('/admin/input_studies/units/add')
@login_required
def input_studies_add_unit():
    """社会科単元追加画面"""
    try:
        textbook_id = request.args.get('textbook_id', type=int)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                if textbook_id:
                    # 特定の教材の単元を追加する場合
                    placeholder = get_placeholder()
                    cur.execute(f'SELECT id, name, subject FROM input_textbooks WHERE id = {placeholder}', (textbook_id,))
                    textbook_data = cur.fetchone()
                    
                    if not textbook_data:
                        flash('教材が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_admin_unified'))
                    
                    textbook = {
                        'id': textbook_data[0],
                        'name': textbook_data[1],
                        'subject': textbook_data[2]
                    }
                    
                    return render_template('input_studies/add_unit.html', textbook=textbook)
                else:
                    # 教材一覧を取得
                    cur.execute('SELECT id, name, subject FROM input_textbooks ORDER BY subject, name')
                    textbooks = cur.fetchall()
                    
                    return render_template('input_studies/add_unit.html', textbooks=textbooks)
                
    except Exception as e:
        current_app.logger.error(f"社会科単元追加画面エラー: {e}")
        flash('社会科単元追加画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_unified'))

@admin_bp.route('/admin/input_studies/units/add', methods=['POST'])
@login_required
def input_studies_add_unit_post():
    """社会科単元追加処理"""
    try:
        name = request.form.get('name', '').strip()
        chapter_number = request.form.get('chapter_number', '').strip()
        description = request.form.get('description', '').strip()
        textbook_id = request.args.get('textbook_id', type=int)
        
        # バリデーション
        if not name:
            flash('単元名は必須です', 'error')
            return redirect(url_for('admin.input_studies_add_unit', textbook_id=textbook_id))
        
        if not textbook_id:
            flash('教材IDが指定されていません', 'error')
            return redirect(url_for('admin.input_studies_admin_unified'))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材が存在するかチェック
                cur.execute('SELECT id FROM input_textbooks WHERE id = ?', (textbook_id,))
                if not cur.fetchone():
                    flash('指定された教材が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_unified'))
                
                # 単元名の重複チェック（同じ教材内で）
                cur.execute('SELECT id FROM input_units WHERE name = ? AND textbook_id = ?', (name, textbook_id))
                if cur.fetchone():
                    flash('この単元名は既に使用されています', 'error')
                    return redirect(url_for('admin.input_studies_add_unit', textbook_id=textbook_id))
                
                # 章番号の処理
                chapter_num = None
                if chapter_number:
                    try:
                        chapter_num = int(chapter_number)
                    except ValueError:
                        flash('章番号は数値で入力してください', 'error')
                        return redirect(url_for('admin.input_studies_add_unit', textbook_id=textbook_id))
                
                # 単元を追加
                cur.execute('''
                    INSERT INTO input_units (textbook_id, name, chapter_number, description)
                    VALUES (?, ?, ?, ?)
                ''', (textbook_id, name, chapter_num, description))
                
                conn.commit()
                flash('単元を追加しました', 'success')
                return redirect(url_for('admin.input_studies_admin_textbook_unified', textbook_id=textbook_id))
                
    except Exception as e:
        current_app.logger.error(f"社会科単元追加エラー: {e}")
        flash('単元の追加に失敗しました', 'error')
        return redirect(url_for('admin.input_studies_add_unit', textbook_id=textbook_id))

@admin_bp.route('/admin/input_studies/units/<int:unit_id>/questions')
@login_required
def input_studies_admin_unit_questions(unit_id):
    """社会科単元問題管理画面"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元情報を取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT u.id, u.name, u.description, t.id as textbook_id, t.name as textbook_name
                    FROM input_units u
                    JOIN input_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = {placeholder}
                ''', (unit_id,))
                unit_data = cur.fetchone()
                
                if not unit_data:
                    flash('単元が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_unified'))
                
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
                cur.execute(f'''
                    SELECT id, question, correct_answer, explanation, difficulty_level, 
                           image_name, image_title, image_url, created_at
                    FROM input_questions 
                    WHERE unit_id = {placeholder}
                    ORDER BY created_at DESC
                ''', (unit_id,))
                questions_data = cur.fetchall()
                
                questions = []
                for q_data in questions_data:
                    questions.append({
                        'id': q_data[0],
                        'question_text': q_data[1],  # questionカラムをquestion_textとして扱う
                        'answer_text': q_data[2],    # correct_answerカラムをanswer_textとして扱う
                        'explanation': q_data[3],
                        'difficulty': q_data[4],     # difficulty_levelカラムをdifficultyとして扱う
                        'image_name': q_data[5],
                        'image_title': q_data[6],
                        'image_url': q_data[7],
                        'created_at': q_data[8]
                    })
                
                # 画像パス情報を取得
                from app import get_unit_image_folder_path_by_unit_id
                folder_path = get_unit_image_folder_path_by_unit_id(unit_id)
                
                # 画像が設定されている問題数を取得
                cur.execute(f'''
                    SELECT COUNT(*) 
                    FROM input_questions 
                    WHERE unit_id = {placeholder} AND (image_name IS NOT NULL OR image_title IS NOT NULL)
                ''', (unit_id,))
                image_questions_count = cur.fetchone()[0]
                
                image_path_info = {
                    'base_url': f"https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/{folder_path}",
                    'folder_path': folder_path,
                    'image_questions_count': image_questions_count
                }
                
                return render_template('input_studies/admin_unit_questions.html', 
                                     textbook_info=textbook_info,
                                     unit_info=unit_info,
                                     questions=questions,
                                     image_path_info=image_path_info)
                
    except Exception as e:
        current_app.logger.error(f"社会科単元問題管理画面エラー: {e}")
        flash('社会科単元問題管理画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_unified')) 

@admin_bp.route('/admin/input_studies/textbooks/<int:textbook_id>/units/csv')
@login_required
def download_units_csv(textbook_id):
    """単元CSVダウンロード"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材情報を取得
                placeholder = get_placeholder()
                cur.execute(f'SELECT name FROM input_textbooks WHERE id = {placeholder}', (textbook_id,))
                textbook_data = cur.fetchone()
                
                if not textbook_data:
                    flash('教材が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_unified'))
                
                # 単元一覧を取得
                cur.execute(f'''
                    SELECT name, chapter_number, description
                    FROM input_units 
                    WHERE textbook_id = {placeholder}
                    ORDER BY chapter_number, name
                ''', (textbook_id,))
                units_data = cur.fetchall()
                
                # CSVデータを作成（BOM付きUTF-8で文字化けを防ぐ）
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['章番号', '単元名', '説明'])
                
                for unit_data in units_data:
                    writer.writerow([
                        unit_data[1] or '',
                        unit_data[0] or '',
                        unit_data[2] or ''
                    ])
                
                # BOM付きUTF-8でエンコード
                csv_content = output.getvalue()
                output_bytes = io.BytesIO()
                output_bytes.write(b'\xef\xbb\xbf')  # BOM
                output_bytes.write(csv_content.encode('utf-8'))
                output_bytes.seek(0)
                
                from flask import Response
                return Response(
                    output_bytes.getvalue(),
                    mimetype='text/csv; charset=utf-8',
                    headers={
                        'Content-Disposition': f'attachment; filename=units_{textbook_id}.csv',
                        'Content-Type': 'text/csv; charset=utf-8'
                    }
                )
                
    except Exception as e:
        current_app.logger.error(f"単元CSVダウンロードエラー: {e}")
        flash('CSVダウンロードに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_textbook_unified', textbook_id=textbook_id))

@admin_bp.route('/admin/input_studies/units/<int:unit_id>/questions/csv')
@login_required
def download_unit_questions_csv(unit_id):
    """単元問題CSVダウンロード"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元情報を取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT u.name, t.id as textbook_id, t.name as textbook_name
                    FROM input_units u
                    JOIN input_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = {placeholder}
                ''', (unit_id,))
                unit_data = cur.fetchone()
                
                if not unit_data:
                    flash('単元が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_unified'))
                
                # 単元の章番号を取得
                cur.execute(f'''
                    SELECT chapter_number FROM input_units WHERE id = {placeholder}
                ''', (unit_id,))
                chapter_number = cur.fetchone()[0]
                
                # 問題一覧を取得
                cur.execute(f'''
                    SELECT question, correct_answer, acceptable_answers, answer_suffix, 
                           explanation, difficulty_level, image_name, question_number
                    FROM input_questions 
                    WHERE unit_id = {placeholder}
                    ORDER BY question_number, created_at
                ''', (unit_id,))
                questions_data = cur.fetchall()
                
                # CSVデータを作成（BOM付きUTF-8で文字化けを防ぐ）
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['問題番号', '問題文', '正解', '難易度', '許容回答', '解答欄の補足', '解説', '画像パス'])
                
                for question_data in questions_data:
                    writer.writerow([
                        question_data[7] or '',  # 問題番号
                        question_data[0] or '',  # 問題文
                        question_data[1] or '',  # 正解
                        question_data[5] or 'normal',  # 難易度
                        question_data[2] or '',  # 許容回答
                        question_data[3] or '',  # 解答欄の補足
                        question_data[4] or '',  # 解説
                        question_data[6] or ''  # 画像パス
                    ])
                
                # BOM付きUTF-8でエンコード
                csv_content = output.getvalue()
                output_bytes = io.BytesIO()
                output_bytes.write(b'\xef\xbb\xbf')  # BOM
                output_bytes.write(csv_content.encode('utf-8'))
                output_bytes.seek(0)
                
                from flask import Response
                return Response(
                    output_bytes.getvalue(),
                    mimetype='text/csv; charset=utf-8',
                    headers={
                        'Content-Disposition': f'attachment; filename=questions_unit_{unit_id}.csv',
                        'Content-Type': 'text/csv; charset=utf-8'
                    }
                )
                
    except Exception as e:
        current_app.logger.error(f"単元問題CSVダウンロードエラー: {e}")
        flash('CSVダウンロードに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_unit_questions', unit_id=unit_id))

@admin_bp.route('/input_studies/admin/edit_textbook/<int:textbook_id>')
@login_required
def input_studies_edit_textbook_get(textbook_id):
    """教材編集データ取得（API）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, name, subject, grade, publisher, description
                    FROM input_textbooks 
                    WHERE id = ?
                ''', (textbook_id,))
                textbook_data = cur.fetchone()
                
                if not textbook_data:
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                textbook = {
                    'id': textbook_data[0],
                    'name': textbook_data[1],
                    'subject': textbook_data[2],
                    'grade': textbook_data[3],
                    'publisher': textbook_data[4],
                    'description': textbook_data[5]
                }
                
                return jsonify(textbook)
                
    except Exception as e:
        current_app.logger.error(f"教材編集データ取得エラー: {e}")
        return jsonify({'error': '教材データの取得に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/edit_textbook/<int:textbook_id>', methods=['POST'])
@login_required
def input_studies_edit_textbook_post(textbook_id):
    """教材編集処理（API）"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        subject = data.get('subject', '').strip()
        grade = data.get('grade', '').strip()
        publisher = data.get('publisher', '').strip()
        description = data.get('description', '').strip()
        
        # バリデーション
        if not name:
            return jsonify({'error': '教材名は必須です'}), 400
        
        if not subject:
            return jsonify({'error': '科目は必須です'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材が存在するかチェック
                cur.execute('SELECT id FROM input_textbooks WHERE id = ?', (textbook_id,))
                if not cur.fetchone():
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                # 教材名の重複チェック（自分以外）
                cur.execute('SELECT id FROM input_textbooks WHERE name = ? AND id != ?', (name, textbook_id))
                if cur.fetchone():
                    return jsonify({'error': 'この教材名は既に使用されています'}), 400
                
                # 教材を更新
                cur.execute('''
                    UPDATE input_textbooks 
                    SET name = ?, subject = ?, grade = ?, publisher = ?, description = ?
                    WHERE id = ?
                ''', (name, subject, grade, publisher, description, textbook_id))
                
                conn.commit()
                return jsonify({'message': '教材を更新しました'})
                
    except Exception as e:
        current_app.logger.error(f"教材編集エラー: {e}")
        return jsonify({'error': '教材の更新に失敗しました'}), 500 

@admin_bp.route('/input_studies/admin/edit_unit/<int:unit_id>')
@login_required
def input_studies_edit_unit_get(unit_id):
    """単元編集データ取得（API）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, name, chapter_number, description, textbook_id
                    FROM input_units 
                    WHERE id = ?
                ''', (unit_id,))
                unit_data = cur.fetchone()
                
                if not unit_data:
                    return jsonify({'error': '単元が見つかりません'}), 404
                
                unit = {
                    'id': unit_data[0],
                    'name': unit_data[1],
                    'chapter_number': unit_data[2],
                    'description': unit_data[3],
                    'textbook_id': unit_data[4]
                }
                
                return jsonify(unit)
                
    except Exception as e:
        current_app.logger.error(f"単元編集データ取得エラー: {e}")
        return jsonify({'error': '単元データの取得に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/edit_unit/<int:unit_id>', methods=['POST'])
@login_required
def input_studies_edit_unit_post(unit_id):
    """単元編集処理（API）"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        chapter_number = data.get('chapter_number', '').strip()
        description = data.get('description', '').strip()
        
        # バリデーション
        if not name:
            return jsonify({'error': '単元名は必須です'}), 400
        
        if not chapter_number:
            return jsonify({'error': '単元番号は必須です'}), 400
        
        try:
            chapter_number = int(chapter_number)
        except ValueError:
            return jsonify({'error': '単元番号は数値で入力してください'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元が存在するかチェック
                cur.execute('SELECT id, textbook_id FROM input_units WHERE id = ?', (unit_id,))
                unit_info = cur.fetchone()
                if not unit_info:
                    return jsonify({'error': '単元が見つかりません'}), 404
                
                textbook_id = unit_info[1]
                
                # 単元番号の重複チェック（同じ教材内で、自分以外）
                cur.execute('SELECT id FROM input_units WHERE textbook_id = ? AND chapter_number = ? AND id != ?', 
                          (textbook_id, chapter_number, unit_id))
                if cur.fetchone():
                    return jsonify({'error': 'この単元番号は既に使用されています'}), 400
                
                # 単元を更新
                cur.execute('''
                    UPDATE input_units 
                    SET name = ?, chapter_number = ?, description = ?
                    WHERE id = ?
                ''', (name, chapter_number, description, unit_id))
                
                conn.commit()
                return jsonify({'message': '単元を更新しました'})
                
    except Exception as e:
        current_app.logger.error(f"単元編集エラー: {e}")
        return jsonify({'error': '単元の更新に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/delete_unit/<int:unit_id>', methods=['DELETE'])
@login_required
def input_studies_delete_unit(unit_id):
    """単元削除処理（API）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元が存在するかチェック
                cur.execute('SELECT id, name FROM input_units WHERE id = ?', (unit_id,))
                unit_info = cur.fetchone()
                if not unit_info:
                    return jsonify({'error': '単元が見つかりません'}), 404
                
                # 単元に関連する問題があるかチェック
                cur.execute('SELECT COUNT(*) FROM input_questions WHERE unit_id = ?', (unit_id,))
                question_count = cur.fetchone()[0]
                
                if question_count > 0:
                    return jsonify({'error': f'この単元には{question_count}件の問題が含まれているため削除できません'}), 400
                
                # 単元を削除
                cur.execute('DELETE FROM input_units WHERE id = ?', (unit_id,))
                conn.commit()
                
                return jsonify({'message': '単元を削除しました'})
                
    except Exception as e:
        current_app.logger.error(f"単元削除エラー: {e}")
        return jsonify({'error': '単元の削除に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/bulk_delete_questions', methods=['POST'])
@login_required
def input_studies_bulk_delete_questions():
    """問題一括削除処理（API）"""
    try:
        data = request.get_json()
        question_ids = data.get('question_ids', [])
        
        if not question_ids:
            return jsonify({'error': '削除する問題が選択されていません'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題を一括削除
                placeholders = ','.join(['?' for _ in question_ids])
                cur.execute(f'DELETE FROM input_questions WHERE id IN ({placeholders})', question_ids)
                deleted_count = cur.rowcount
                
                conn.commit()
                return jsonify({'message': f'{deleted_count}件の問題を削除しました'})
                
    except Exception as e:
        current_app.logger.error(f"問題一括削除エラー: {e}")
        return jsonify({'error': '問題の削除に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/upload_csv', methods=['POST'])
@login_required
def input_studies_upload_csv():
    """CSVアップロード処理（API）"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'CSVファイルを選択してください'}), 400
        
        textbook_id = request.form.get('textbook_id')
        if not textbook_id:
            return jsonify({'error': '教材IDが指定されていません'}), 400
        
        # CSVファイルを処理
        import csv
        import io
        
        # ファイルの内容を読み込み、BOMを除去してUTF-8でデコード
        content = file.read()
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]  # BOMを除去
        content = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                for row in csv_reader:
                    if len(row) >= 2:
                        name = row[0].strip()
                        unit_number = row[1].strip()
                        description = row[2].strip() if len(row) > 2 else ''
                        
                        if name and unit_number:
                            try:
                                unit_number = int(unit_number)
                                cur.execute('''
                                    INSERT INTO input_units (textbook_id, name, chapter_number, description)
                                    VALUES (?, ?, ?, ?)
                                ''', (textbook_id, name, unit_number, description))
                            except ValueError:
                                continue
                
                conn.commit()
                return jsonify({'message': 'CSVファイルをアップロードしました'})
                
    except Exception as e:
        current_app.logger.error(f"CSVアップロードエラー: {e}")
        return jsonify({'error': 'CSVアップロードに失敗しました'}), 500

@admin_bp.route('/input_studies/admin/upload_units_csv', methods=['POST'])
@login_required
def input_studies_upload_units_csv():
    """単元CSVアップロード処理（API）"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'CSVファイルを選択してください'}), 400
        
        textbook_id = request.form.get('textbook_id')
        if not textbook_id:
            return jsonify({'error': '教材IDが指定されていません'}), 400
        
        # CSVファイルを処理
        import csv
        import io
        
        # ファイルの内容を読み込み、BOMを除去してUTF-8でデコード
        content = file.read()
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]  # BOMを除去
        content = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                for row in csv_reader:
                    if len(row) >= 2:
                        unit_number = row[0].strip()
                        name = row[1].strip()
                        description = row[2].strip() if len(row) > 2 else ''
                        
                        if name:  # 単元名のみ必須
                            # 章番号が空の場合は自動的に次の番号を割り当て
                            if unit_number:
                                try:
                                    unit_number_int = int(unit_number)
                                except ValueError:
                                    # 章番号が数値でない場合は自動割り当て
                                    cur.execute('''
                                        SELECT COALESCE(MAX(chapter_number), 0) + 1 
                                        FROM input_units 
                                        WHERE textbook_id = ?
                                    ''', (textbook_id,))
                                    unit_number_int = cur.fetchone()[0]
                            else:
                                # 章番号が空の場合は自動割り当て
                                cur.execute('''
                                    SELECT COALESCE(MAX(chapter_number), 0) + 1 
                                    FROM input_units 
                                    WHERE textbook_id = ?
                                ''', (textbook_id,))
                                unit_number_int = cur.fetchone()[0]
                            
                            cur.execute('''
                                INSERT INTO input_units (textbook_id, name, chapter_number, description)
                                VALUES (?, ?, ?, ?)
                            ''', (textbook_id, name, unit_number_int, description))
                
                conn.commit()
                return jsonify({'message': '単元CSVファイルをアップロードしました'})
                
    except Exception as e:
        current_app.logger.error(f"単元CSVアップロードエラー: {e}")
        return jsonify({'error': '単元CSVアップロードに失敗しました'}), 500

@admin_bp.route('/input_studies/admin/upload_questions_csv', methods=['POST'])
@login_required
def input_studies_upload_questions_csv():
    """問題CSVアップロード処理（API）"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'ファイルが選択されていません'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'CSVファイルを選択してください'}), 400
        
        unit_id = request.form.get('unit_id')
        if not unit_id:
            return jsonify({'error': '単元IDが指定されていません'}), 400
        
        # CSVファイルを処理
        import csv
        import io
        
        # ファイルの内容を読み込み、BOMを除去してUTF-8でデコード
        content = file.read()
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]  # BOMを除去
        content = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        
        success_count = 0
        error_count = 0
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 単元情報を取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT u.textbook_id, t.subject, t.name as textbook_name, u.name as unit_name
                    FROM input_units u
                    JOIN input_textbooks t ON u.textbook_id = t.id
                    WHERE u.id = {placeholder}
                ''', (unit_id,))
                unit_info = cur.fetchone()
                
                if not unit_info:
                    return jsonify({'error': '単元情報が見つかりません'}), 400
                
                textbook_id = unit_info[0]
                subject = unit_info[1]
                textbook_name = unit_info[2]
                unit_name = unit_info[3]
                
                for row_num, row in enumerate(csv_reader, 1):
                    if row_num == 1:  # ヘッダー行をスキップ
                        continue
                    
                    if len(row) >= 2:  # 最低限必要な列数（問題番号,問題文）
                        # CSVの列: 問題番号,問題文,正解,難易度,許容回答,解答欄の補足,解説,画像パス
                        question_number = row[0].strip() if len(row) > 0 else ''
                        question = row[1].strip() if len(row) > 1 else ''  # 問題文
                        answer = row[2].strip() if len(row) > 2 else ''    # 正解
                        difficulty = row[3].strip() if len(row) > 3 else ''
                        acceptable_answers = row[4].strip() if len(row) > 4 else ''
                        answer_suffix = row[5].strip() if len(row) > 5 else ''
                        explanation = row[6].strip() if len(row) > 6 else ''
                        image_path = row[7].strip() if len(row) > 7 else ''
                        
                        if question and answer:  # 問題文と正解が存在する場合のみ処理
                            # 教材と単元のIDを取得（固定値として使用）
                            textbook_id_to_use = textbook_id
                            unit_id_to_use = unit_id
                            
                            # 問題番号を数値に変換（空の場合はNone）
                            try:
                                question_number_int = int(question_number) if question_number else None
                            except ValueError:
                                question_number_int = None
                            
                            # 難易度の検証（空の場合はそのまま）
                            if difficulty and difficulty not in ['basic', 'intermediate', 'advanced']:
                                difficulty = ''
                            
                            cur.execute('''
                                INSERT INTO input_questions 
                                (unit_id, textbook_id, subject, question, correct_answer, acceptable_answers, 
                                 answer_suffix, explanation, difficulty_level, image_path, question_number, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ''', (unit_id_to_use, textbook_id_to_use, subject, question, answer, acceptable_answers,
                                  answer_suffix, explanation, difficulty, image_path, question_number_int))
                            
                            success_count += 1
                        else:
                            error_count += 1
                
                conn.commit()
                return jsonify({
                    'message': f'問題CSVファイルをアップロードしました（成功: {success_count}件、失敗: {error_count}件）',
                    'success_count': success_count,
                    'error_count': error_count
                })
                
    except Exception as e:
        current_app.logger.error(f"問題CSVアップロードエラー: {e}")
        return jsonify({'error': '問題CSVアップロードに失敗しました'}), 500

@admin_bp.route('/input_studies/admin/download_csv_template')
@login_required
def input_studies_download_csv_template():
    """CSVテンプレートダウンロード"""
    try:
        import csv
        import io
        
        # CSVデータを作成（BOM付きUTF-8で文字化けを防ぐ）
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー行
        writer.writerow(['問題番号', '問題文', '正解', '難易度', '許容回答', '解答欄の補足', '解説', '画像パス'])
        
        # サンプルデータ
        writer.writerow(['1', '日本の首都は？', '東京', 'basic', '東京都,Tokyo', '', '日本の首都は東京です', '/static/images/1.jpg'])
        writer.writerow(['2', '日本で最も高い山は？', '富士山', 'intermediate', '富士山,ふじさん', '山', '富士山は日本一高い山です', 'https://example.com/fuji.jpg'])
        
        # BOM付きUTF-8でエンコード
        csv_content = output.getvalue()
        output_bytes = io.BytesIO()
        output_bytes.write(b'\xef\xbb\xbf')  # BOM
        output_bytes.write(csv_content.encode('utf-8'))
        output_bytes.seek(0)
        
        from flask import Response
        return Response(
            output_bytes.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': 'attachment; filename=input_studies_questions_template.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"CSVテンプレートダウンロードエラー: {e}")
        flash('CSVテンプレートダウンロードに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_questions'))

@admin_bp.route('/input_studies/admin/question/<int:question_id>')
@login_required
def input_studies_get_question(question_id):
    """問題データ取得（API）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT id, question, answer, explanation, question_type, image_path
                    FROM input_questions 
                    WHERE id = ?
                ''', (question_id,))
                question_data = cur.fetchone()
                
                if not question_data:
                    return jsonify({'error': '問題が見つかりません'}), 404
                
                question = {
                    'id': question_data[0],
                    'question': question_data[1],
                    'answer': question_data[2],
                    'explanation': question_data[3],
                    'question_type': question_data[4],
                    'image_path': question_data[5]
                }
                
                return jsonify(question)
                
    except Exception as e:
        current_app.logger.error(f"問題データ取得エラー: {e}")
        return jsonify({'error': '問題データの取得に失敗しました'}), 500

@admin_bp.route('/input_studies/admin/upload_image/<int:question_id>', methods=['POST'])
@login_required
def input_studies_upload_image(question_id):
    """問題画像アップロード処理（API）"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': '画像ファイルが選択されていません'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': '画像ファイルが選択されていません'}), 400
        
        # 画像ファイルの処理（実際の実装では画像保存処理が必要）
        # ここでは簡易的にファイル名を保存
        image_path = f"uploads/questions/{question_id}_{file.filename}"
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    UPDATE input_questions 
                    SET image_path = ?
                    WHERE id = ?
                ''', (image_path, question_id))
                
                conn.commit()
                return jsonify({'message': '画像をアップロードしました', 'image_path': image_path})
                
    except Exception as e:
        current_app.logger.error(f"画像アップロードエラー: {e}")
        return jsonify({'error': '画像アップロードに失敗しました'}), 500

@admin_bp.route('/input_studies/admin/delete_image/<int:question_id>', methods=['POST'])
@login_required
def input_studies_delete_image(question_id):
    """問題画像削除処理（API）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    UPDATE input_questions 
                    SET image_path = NULL
                    WHERE id = ?
                ''', (question_id,))
                
                conn.commit()
                return jsonify({'message': '画像を削除しました'})
                
    except Exception as e:
        current_app.logger.error(f"画像削除エラー: {e}")
        return jsonify({'error': '画像削除に失敗しました'}), 500

@admin_bp.route('/admin/input_studies/questions/<int:question_id>/edit')
@login_required
def input_studies_edit_question_page(question_id):
    """社会科問題編集画面（GET）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題データを取得
                placeholder = get_placeholder()
                cur.execute(f'''
                    SELECT q.id, q.question, q.correct_answer, q.explanation, q.subject, 
                           q.difficulty_level, q.textbook_id, q.unit_id,
                           q.image_name, q.image_title, q.image_url,
                           t.name as textbook_name, u.name as unit_name
                    FROM input_questions q
                    LEFT JOIN input_textbooks t ON q.textbook_id = t.id
                    LEFT JOIN input_units u ON q.unit_id = u.id
                    WHERE q.id = {placeholder}
                ''', (question_id,))
                question_data = cur.fetchone()
                
                if not question_data:
                    flash('問題が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_questions'))
                
                question = {
                    'id': question_data[0],
                    'question_text': question_data[1],  # questionカラムをquestion_textとして扱う
                    'answer_text': question_data[2],    # correct_answerカラムをanswer_textとして扱う
                    'explanation': question_data[3],
                    'subject': question_data[4],
                    'difficulty': question_data[5],     # difficulty_levelカラムをdifficultyとして扱う
                    'textbook_id': question_data[6],
                    'unit_id': question_data[7],
                    'image_name': question_data[8],
                    'image_title': question_data[9],
                    'image_url': question_data[10],
                    'textbook_name': question_data[11] or '未設定',
                    'unit_name': question_data[12] or '未設定'
                }
                
                # 教材情報を取得
                textbook_info = None
                if question['textbook_id']:
                    cur.execute(f'SELECT id, name, subject FROM input_textbooks WHERE id = {placeholder}', (question['textbook_id'],))
                    textbook_data = cur.fetchone()
                    if textbook_data:
                        textbook_info = {
                            'id': textbook_data[0],
                            'name': textbook_data[1],
                            'subject': textbook_data[2]
                        }
                
                # 単元情報を取得
                unit_info = None
                if question['unit_id']:
                    cur.execute(f'SELECT id, name, chapter_number FROM input_units WHERE id = {placeholder}', (question['unit_id'],))
                    unit_data = cur.fetchone()
                    if unit_data:
                        unit_info = {
                            'id': unit_data[0],
                            'name': unit_data[1],
                            'chapter_number': unit_data[2]
                        }
                
                # 画像パス情報を取得
                image_path_info = None
                if question['unit_id']:
                    from app import get_unit_image_folder_path_by_unit_id
                    folder_path = get_unit_image_folder_path_by_unit_id(question['unit_id'])
                    image_path_info = {
                        'base_url': f"https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/{folder_path}",
                        'folder_path': folder_path
                    }
                
                return render_template('input_studies/edit_question.html', 
                                     question=question, textbook_info=textbook_info, unit_info=unit_info, image_path_info=image_path_info)
                
    except Exception as e:
        current_app.logger.error(f"社会科問題編集画面エラー: {e}")
        flash('問題編集画面の読み込みに失敗しました', 'error')
        return redirect(url_for('admin.input_studies_admin_questions'))

@admin_bp.route('/admin/input_studies/questions/<int:question_id>/edit', methods=['POST'])
@login_required
def input_studies_edit_question_post(question_id):
    """社会科問題編集処理"""
    try:
        # JSONデータとフォームデータの両方に対応
        if request.is_json:
            data = request.get_json()
            question_text = data.get('question_text', '').strip()
            answer_text = data.get('answer_text', '').strip()
            explanation = data.get('explanation', '').strip()
            subject = data.get('subject', '').strip()
            difficulty = data.get('difficulty', 'normal')
            textbook_id = data.get('textbook_id')
            unit_id = data.get('unit_id')
        else:
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
            return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id))
        
        if not answer_text:
            flash('正解は必須です', 'error')
            return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id))
        
        if not subject:
            flash('科目は必須です', 'error')
            return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id))
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 問題が存在するかチェック
                placeholder = get_placeholder()
                cur.execute(f'SELECT id FROM input_questions WHERE id = {placeholder}', (question_id,))
                if not cur.fetchone():
                    flash('問題が見つかりません', 'error')
                    return redirect(url_for('admin.input_studies_admin_questions'))
                
                # 教材・単元の存在チェック
                if textbook_id:
                    cur.execute(f'SELECT id FROM input_textbooks WHERE id = {placeholder}', (textbook_id,))
                    if not cur.fetchone():
                        flash('指定された教材が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id))
                
                if unit_id:
                    cur.execute(f'SELECT id FROM input_units WHERE id = {placeholder}', (unit_id,))
                    if not cur.fetchone():
                        flash('指定された単元が見つかりません', 'error')
                        return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id))
                
                # 問題を更新
                cur.execute(f'''
                    UPDATE input_questions 
                    SET question = {placeholder}, correct_answer = {placeholder}, explanation = {placeholder}, 
                        subject = {placeholder}, difficulty_level = {placeholder}, 
                        textbook_id = {placeholder}, unit_id = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                ''', (question_text, answer_text, explanation, subject, difficulty, textbook_id, unit_id, question_id))
                
                conn.commit()
                
                # JSONリクエストの場合はJSONレスポンスを返す
                if request.is_json:
                    return jsonify({'message': '問題を更新しました'})
                else:
                    flash('問題を更新しました', 'success')
                    return redirect(url_for('admin.input_studies_admin_questions'))
                
    except Exception as e:
        current_app.logger.error(f"社会科問題編集エラー: {e}")
        if request.is_json:
            return jsonify({'error': '問題の更新に失敗しました'}), 500
        else:
            flash('問題の更新に失敗しました', 'error')
            return redirect(url_for('admin.input_studies_edit_question_page', question_id=question_id)) 

@admin_bp.route('/input_studies/admin/update_image_path/<int:textbook_id>/<int:unit_id>', methods=['POST'])
@login_required
def input_studies_update_image_path(textbook_id, unit_id):
    """画像パス一括更新処理"""
    try:
        data = request.get_json()
        new_image_path = data.get('image_path', '').strip()
        update_questions = data.get('update_questions', False)
        
        if not new_image_path:
            return jsonify({'error': '画像パスが指定されていません'}), 400
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 教材と単元が存在するかチェック
                placeholder = get_placeholder()
                cur.execute(f'SELECT id FROM input_textbooks WHERE id = {placeholder}', (textbook_id,))
                if not cur.fetchone():
                    return jsonify({'error': '教材が見つかりません'}), 404
                
                cur.execute(f'SELECT id FROM input_units WHERE id = {placeholder}', (unit_id,))
                if not cur.fetchone():
                    return jsonify({'error': '単元が見つかりません'}), 404
                
                updated_questions_count = 0
                
                if update_questions:
                    # この単元の全問題の画像パスを一括更新
                    cur.execute(f'''
                        UPDATE input_questions 
                        SET image_path = {placeholder}, updated_at = CURRENT_TIMESTAMP
                        WHERE unit_id = {placeholder}
                    ''', (new_image_path, unit_id))
                    
                    updated_questions_count = cur.rowcount
                
                conn.commit()
                
                return jsonify({
                    'message': '画像パスを一括更新しました',
                    'updated_questions_count': updated_questions_count
                })
                
    except Exception as e:
        current_app.logger.error(f"画像パス一括更新エラー: {e}")
        return jsonify({'error': '画像パスの一括更新に失敗しました'}), 500 