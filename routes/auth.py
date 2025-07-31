from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import User  # Userクラスはmodels/user.pyに移動予定
from utils.db import get_db_connection, get_db_cursor, get_placeholder

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.pop('_flashes', None)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            with get_db_connection() as conn:
                with get_db_cursor(conn) as cur:
                    placeholder = get_placeholder()
                    cur.execute(f"SELECT id, username, password_hash, full_name, is_admin FROM users WHERE username = {placeholder}", (username,))
                    user = cur.fetchone()
                    
                    # デバッグ用のログ出力
                    current_app.logger.info(f"データベース検索結果: username={username}, user_found={user is not None}")
                    if user:
                        current_app.logger.info(f"ユーザー情報: id={user[0]}, username={user[1]}, is_admin={user[4]}")
                        current_app.logger.info(f"パスワードハッシュ: {user[2]}")
                        current_app.logger.info(f"パスワードハッシュの長さ: {len(user[2]) if user[2] else 0}")
                    else:
                        current_app.logger.warning(f"ユーザー '{username}' が見つかりませんでした")

            if user and check_password_hash(user[2], password):
                login_user(User(user[0], user[1], user[2], user[3], user[4]))
                current_app.logger.info(f"ログイン成功: user_id={user[0]}, username={user[1]}, is_admin={user[4]}")
            elif user:
                current_app.logger.warning(f"パスワードが一致しません: username={username}")
                current_app.logger.info(f"入力されたパスワードの長さ: {len(password)}")
                current_app.logger.info(f"パスワードハッシュの長さ: {len(user[2]) if user[2] else 0}")
                
                # 最終ログイン時刻を更新
                with get_db_connection() as conn:
                    with get_db_cursor(conn) as cur:
                        placeholder = get_placeholder()
                        cur.execute(f"UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = {placeholder}", (user[0],))
                        conn.commit()
                
                # 管理者の場合は管理者画面にリダイレクト
                if user[4]:  # is_adminがTrueの場合
                    current_app.logger.info("管理者ユーザー: 管理画面にリダイレクト")
                    return redirect(url_for('admin.admin'))
                
                # 通常ユーザーの場合はnextパラメータまたはホーム画面にリダイレクト
                next_page = request.args.get('next')
                if next_page:
                    current_app.logger.info(f"nextパラメータ: {next_page}にリダイレクト")
                    return redirect(next_page)
                
                current_app.logger.info("通常ユーザー: ホーム画面にリダイレクト")
                return redirect(url_for('home'))
            else:
                current_app.logger.warning(f"ログイン失敗: username={username}")
                flash("ログインに失敗しました。")
        except Exception as e:
            current_app.logger.error(f"ログインエラー: {e}")
            flash("ログイン中にエラーが発生しました")

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form.get('full_name', username)  # full_nameフィールドがあれば使用、なければusername

        try:
            with get_db_connection() as conn:
                with get_db_cursor(conn) as cur:
                    # ユーザー名の重複チェック
                    placeholder = get_placeholder()
                    cur.execute(f"SELECT id FROM users WHERE username = {placeholder}", (username,))
                    if cur.fetchone():
                        flash('このユーザー名は既に使用されています', 'error')
                        return render_template('register.html')
                    
                    # パスワードハッシュ生成
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    
                    # ユーザー登録前の確認
                    cur.execute("SELECT COUNT(*) FROM users")
                    user_count_before = cur.fetchone()[0]
                    current_app.logger.info(f"登録前のユーザー数: {user_count_before}")
                    
                    # ユーザー登録
                    cur.execute(f"""
                        INSERT INTO users (username, email, password_hash, is_admin, full_name, grade, created_at)
                        VALUES ({placeholder}, NULL, {placeholder}, ?, {placeholder}, ?, CURRENT_TIMESTAMP)
                    """, (username, hashed_password, False, full_name, '一般'))
                    
                    user_id = cur.lastrowid
                    current_app.logger.info(f"ユーザー登録実行: user_id={user_id}, username={username}")
                    
                    # コミット前の確認
                    cur.execute(f"SELECT COUNT(*) FROM users WHERE username = {placeholder}", (username,))
                    count_before_commit = cur.fetchone()[0]
                    current_app.logger.info(f"コミット前のユーザー数（該当ユーザー）: {count_before_commit}")
                    
                    # コミット
                    conn.commit()
                    current_app.logger.info(f"ユーザー登録コミット完了: user_id={user_id}")
                    
                    # コミット後の確認
                    cur.execute(f"SELECT COUNT(*) FROM users WHERE username = {placeholder}", (username,))
                    count_after_commit = cur.fetchone()[0]
                    current_app.logger.info(f"コミット後のユーザー数（該当ユーザー）: {count_after_commit}")
                    
                    cur.execute("SELECT COUNT(*) FROM users")
                    user_count_after = cur.fetchone()[0]
                    current_app.logger.info(f"コミット後の総ユーザー数: {user_count_after}")
                    
                    current_app.logger.info(f"ユーザー登録成功: user_id={user_id}, username={username}")
                    flash('ユーザー登録が完了しました', 'success')
                    
            return redirect(url_for('auth.login'))
        except Exception as e:
            current_app.logger.error(f"ユーザー登録エラー: {e}")
            import traceback
            current_app.logger.error(f"詳細エラー: {traceback.format_exc()}")
            flash(f"登録エラー: {e}")

    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login')) 