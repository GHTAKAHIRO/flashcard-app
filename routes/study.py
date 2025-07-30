from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_required, current_user
from utils.db import get_db_connection, get_db_cursor
from utils.study_utils import (
    has_study_history, clear_user_cache, get_detailed_progress_for_all_stages,
    get_study_cards_fast, get_chunk_practice_cards, create_fallback_stage_info
)
import json
from datetime import datetime

study_bp = Blueprint('study', __name__)

def parse_datetime(datetime_str):
    """文字列の日時をdatetimeオブジェクトに変換"""
    if not datetime_str:
        return None
    try:
        # SQLiteの日時形式を解析
        if isinstance(datetime_str, str):
            # 複数の形式に対応
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d'
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
        return datetime_str
    except Exception:
        return None

@study_bp.route('/dashboard')
@login_required
def dashboard():
    """生徒のダッシュボード - 割り当てられた教材を表示"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 割り当てられた教材を取得
                cur.execute('''
                    SELECT ta.id, ta.textbook_id, ta.assignment_type, ta.units, ta.chunks,
                           ta.assigned_at, ta.expires_at,
                           CASE 
                               WHEN ta.assignment_type = 'input' THEN it.name
                               WHEN ta.assignment_type = 'choice' THEN ct.source
                           END as textbook_name,
                           CASE 
                               WHEN ta.assignment_type = 'input' THEN it.subject
                               WHEN ta.assignment_type = 'choice' THEN '選択問題'
                           END as subject
                    FROM textbook_assignments ta
                    LEFT JOIN input_textbooks it ON ta.textbook_id = it.id AND ta.assignment_type = 'input'
                    LEFT JOIN choice_textbooks ct ON ta.textbook_id = ct.id AND ta.assignment_type = 'choice'
                    WHERE ta.user_id = ? AND ta.is_active = TRUE
                    ORDER BY ta.assigned_at DESC
                ''', (user_id,))
                assignments = cur.fetchall()
                
                # 各割り当ての詳細情報を取得
                processed_assignments = []
                for assignment in assignments:
                    assignment_dict = dict(assignment)
                    assignment_dict['assigned_at'] = parse_datetime(assignment['assigned_at'])
                    assignment_dict['expires_at'] = parse_datetime(assignment['expires_at'])
                    
                    if assignment['units']:
                        try:
                            unit_ids = json.loads(assignment['units'])
                            if assignment['assignment_type'] == 'input':
                                cur.execute('''
                                    SELECT id, name, chapter_number, description 
                                    FROM input_units 
                                    WHERE id IN ({})
                                    ORDER BY chapter_number, name
                                '''.format(','.join(['?' for _ in unit_ids])), unit_ids)
                            else:
                                cur.execute('''
                                    SELECT id, name, unit_number 
                                    FROM choice_units 
                                    WHERE id IN ({})
                                    ORDER BY unit_number, name
                                '''.format(','.join(['?' for _ in unit_ids])), unit_ids)
                            assignment_dict['unit_details'] = cur.fetchall()
                        except json.JSONDecodeError:
                            assignment_dict['unit_details'] = []
                    else:
                        assignment_dict['unit_details'] = []
                    
                    processed_assignments.append(assignment_dict)
                
                return render_template('dashboard.html', 
                                     assignments=processed_assignments,
                                     now=datetime.now())
                
    except Exception as e:
        current_app.logger.error(f"ダッシュボードエラー: {e}")
        flash('ダッシュボードの読み込みに失敗しました', 'error')
        return redirect(url_for('home'))

@study_bp.route('/start_assignment/<int:assignment_id>')
@login_required
def start_assignment(assignment_id):
    """割り当てられた教材の学習開始"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 割り当て情報を取得
                cur.execute('''
                    SELECT ta.*, t.name as textbook_name, t.subject
                    FROM textbook_assignments ta
                    JOIN textbooks t ON ta.textbook_id = t.id
                    WHERE ta.id = ? AND ta.user_id = ? AND ta.is_active = TRUE
                ''', (assignment_id, user_id))
                assignment = cur.fetchone()
                
                if not assignment:
                    flash('割り当てられた教材が見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 期限チェック
                if assignment['expires_at'] and assignment['expires_at'] < datetime.now():
                    flash('この教材の学習期限が過ぎています', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 教材の問題を取得して、問題タイプを判定
                cur.execute('''
                    SELECT q.choices, COUNT(*) as total_questions
                    FROM questions q
                    JOIN units u ON q.unit_id = u.id
                    WHERE u.textbook_id = ? AND q.is_active = TRUE
                    GROUP BY q.choices IS NOT NULL
                ''', (assignment['textbook_id'],))
                question_types = cur.fetchall()
                
                if not question_types:
                    flash('この教材には問題がありません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 問題タイプを判定（選択問題が1つでもあれば選択問題として扱う）
                has_choice_questions = any(qt['choices'] is not None for qt in question_types)
                
                # 学習セッションを作成
                session_id = create_or_get_study_session(user_id, assignment['textbook_id'], 
                                                       'choice' if has_choice_questions else 'input')
                
                # 問題タイプに応じてリダイレクト
                if has_choice_questions:
                    return redirect(url_for('study.start_choice_study', session_id=session_id))
                else:
                    return redirect(url_for('study.start_input_study', session_id=session_id))
                
    except Exception as e:
        current_app.logger.error(f"学習開始エラー: {e}")
        flash('学習の開始に失敗しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/start_assignment_with_type/<int:assignment_id>/<study_type>')
@login_required
def start_assignment_with_type(assignment_id, study_type):
    """指定された学習形式で割り当てられた教材の学習開始"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 割り当て情報を取得
                cur.execute('''
                    SELECT ta.*, 
                           CASE 
                               WHEN ta.assignment_type = 'input' THEN it.name
                               WHEN ta.assignment_type = 'choice' THEN ct.source
                           END as textbook_name,
                           CASE 
                               WHEN ta.assignment_type = 'input' THEN it.subject
                               WHEN ta.assignment_type = 'choice' THEN '選択問題'
                           END as subject
                    FROM textbook_assignments ta
                    LEFT JOIN input_textbooks it ON ta.textbook_id = it.id AND ta.assignment_type = 'input'
                    LEFT JOIN choice_textbooks ct ON ta.textbook_id = ct.id AND ta.assignment_type = 'choice'
                    WHERE ta.id = ? AND ta.user_id = ? AND ta.is_active = TRUE
                ''', (assignment_id, user_id))
                assignment = cur.fetchone()
                
                if not assignment:
                    flash('割り当てられた教材が見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 期限チェック
                if assignment['expires_at'] and assignment['expires_at'] < datetime.now():
                    flash('この教材の学習期限が過ぎています', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 学習セッションを作成または取得
                session_id = create_or_get_study_session(user_id, assignment['textbook_id'], study_type)
                
                # 学習タイプに応じてリダイレクト
                if study_type == 'input':
                    return redirect(url_for('study.start_input_study', session_id=session_id))
                elif study_type == 'choice':
                    return redirect(url_for('study.start_choice_study', session_id=session_id))
                else:
                    flash('無効な学習形式です', 'error')
                    return redirect(url_for('study.dashboard'))
                
    except Exception as e:
        current_app.logger.error(f"学習開始エラー: {e}")
        flash('学習開始中にエラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

def create_or_get_study_session(user_id, textbook_id, study_type):
    """学習セッションを作成または取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 既存のアクティブなセッションをチェック
                cur.execute('''
                    SELECT id FROM study_sessions 
                    WHERE user_id = ? AND textbook_id = ? AND study_type = ? AND completed = FALSE
                ''', (user_id, textbook_id, study_type))
                existing_session = cur.fetchone()
                
                if existing_session:
                    return existing_session['id']
                
                # 新しいセッションを作成
                cur.execute('''
                    INSERT INTO study_sessions (user_id, textbook_id, study_type, progress, completed)
                    VALUES (?, ?, ?, 0.0, FALSE)
                ''', (user_id, textbook_id, study_type))
                
                conn.commit()
                return cur.lastrowid
                
    except Exception as e:
        current_app.logger.error(f"セッション作成エラー: {e}")
        return None

@study_bp.route('/start_input_study/<int:session_id>')
@login_required
def start_input_study(session_id):
    """入力問題学習開始"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # セッション情報を取得
                cur.execute('''
                    SELECT ss.*, t.name as textbook_name, t.subject
                    FROM study_sessions ss
                    JOIN textbooks t ON ss.textbook_id = t.id
                    WHERE ss.id = ? AND ss.user_id = ? AND ss.study_type = 'input'
                ''', (session_id, user_id))
                session_info = cur.fetchone()
                
                if not session_info:
                    flash('学習セッションが見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 問題を取得
                cur.execute('''
                    SELECT q.*, u.name as unit_name
                    FROM questions q
                    JOIN units u ON q.unit_id = u.id
                    WHERE u.textbook_id = ? AND q.is_active = TRUE
                    ORDER BY u.chapter_number, q.question_number
                ''', (session_info['textbook_id'],))
                questions = cur.fetchall()
                
                if not questions:
                    flash('問題が見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # セッション情報をセッションに保存
                session['input_study_session'] = {
                    'session_id': session_id,
                    'textbook_name': session_info['textbook_name'],
                    'subject': session_info['subject'],
                    'questions': [
                        {
                            'id': q['id'],
                            'question': q['question_text'],
                            'correct_answer': q['correct_answer'],
                            'acceptable_answers': q['acceptable_answers'],
                            'answer_suffix': q['answer_suffix'],
                            'explanation': q['explanation'],
                            'image_url': q['image_url'],
                            'unit_name': q['unit_name']
                        }
                        for q in questions
                    ],
                    'current_index': 0,
                    'total_questions': len(questions),
                    'correct_count': 0,
                    'start_time': datetime.now().isoformat()
                }
                
                return redirect(url_for('study.input_study_question'))
                
    except Exception as e:
        current_app.logger.error(f"入力問題学習開始エラー: {e}")
        flash('学習開始中にエラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/start_choice_study/<int:session_id>')
@login_required
def start_choice_study(session_id):
    """選択問題学習開始"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # セッション情報を取得
                cur.execute('''
                    SELECT ss.*, t.name as textbook_name, t.subject
                    FROM study_sessions ss
                    JOIN textbooks t ON ss.textbook_id = t.id
                    WHERE ss.id = ? AND ss.user_id = ? AND ss.study_type = 'choice'
                ''', (session_id, user_id))
                session_info = cur.fetchone()
                
                if not session_info:
                    flash('学習セッションが見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 問題を取得
                cur.execute('''
                    SELECT q.*, u.name as unit_name
                    FROM questions q
                    JOIN units u ON q.unit_id = u.id
                    WHERE u.textbook_id = ? AND q.is_active = TRUE AND q.choices IS NOT NULL
                    ORDER BY u.chapter_number, q.question_number
                ''', (session_info['textbook_id'],))
                questions = cur.fetchall()
                
                if not questions:
                    flash('選択問題が見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # セッション情報をセッションに保存
                session['choice_study_session'] = {
                    'session_id': session_id,
                    'textbook_name': session_info['textbook_name'],
                    'subject': session_info['subject'],
                    'questions': [
                        {
                            'id': q['id'],
                            'question': q['question_text'],
                            'correct_answer': q['correct_answer'],
                            'choices': q['choices'],
                            'explanation': q['explanation'],
                            'unit_name': q['unit_name']
                        }
                        for q in questions
                    ],
                    'current_index': 0,
                    'total_questions': len(questions),
                    'correct_count': 0,
                    'start_time': datetime.now().isoformat()
                }
                
                return redirect(url_for('study.choice_study_question'))
                
    except Exception as e:
        current_app.logger.error(f"選択問題学習開始エラー: {e}")
        flash('学習開始中にエラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/input_study_question')
@login_required
def input_study_question():
    """入力問題学習画面"""
    try:
        session_data = session.get('input_study_session')
        if not session_data:
            flash('学習セッションが見つかりません', 'error')
            return redirect(url_for('study.dashboard'))
        
        current_index = session_data['current_index']
        questions = session_data['questions']
        
        if current_index >= len(questions):
            # 学習完了
            return redirect(url_for('study.complete_study', session_id=session_data['session_id']))
        
        current_question = questions[current_index]
        
        return render_template('study/input_question.html',
                             question=current_question,
                             current_index=current_index + 1,
                             total_questions=len(questions),
                             textbook_name=session_data['textbook_name'],
                             subject=session_data['subject'])
        
    except Exception as e:
        current_app.logger.error(f"入力問題学習画面エラー: {e}")
        flash('エラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/choice_study_question')
@login_required
def choice_study_question():
    """選択問題学習画面"""
    try:
        session_data = session.get('choice_study_session')
        if not session_data:
            flash('学習セッションが見つかりません', 'error')
            return redirect(url_for('study.dashboard'))
        
        current_index = session_data['current_index']
        questions = session_data['questions']
        
        if current_index >= len(questions):
            # 学習完了
            return redirect(url_for('study.complete_study', session_id=session_data['session_id']))
        
        current_question = questions[current_index]
        
        # 選択肢をJSONからパース
        import json
        choices = json.loads(current_question['choices']) if current_question['choices'] else []
        
        return render_template('study/choice_question.html',
                             question=current_question,
                             choices=choices,
                             current_index=current_index + 1,
                             total_questions=len(questions),
                             textbook_name=session_data['textbook_name'],
                             subject=session_data['subject'])
        
    except Exception as e:
        current_app.logger.error(f"選択問題学習画面エラー: {e}")
        flash('エラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    """回答を提出して次の問題に進む"""
    try:
        data = request.get_json()
        answer = data.get('answer', '').strip()
        question_id = data.get('question_id')
        study_type = data.get('study_type')
        
        if study_type == 'input':
            session_data = session.get('input_study_session')
            if not session_data:
                return jsonify({'error': 'セッションが見つかりません'}), 400
            
            current_question = session_data['questions'][session_data['current_index']]
            
            # 正解判定
            is_correct = check_input_answer(answer, current_question['correct_answer'], current_question['acceptable_answers'])
            
            # 学習ログを記録
            log_study_result(session_data['session_id'], question_id, answer, 
                           current_question['correct_answer'], is_correct, 'input')
            
            # セッションを更新
            if is_correct:
                session_data['correct_count'] += 1
            session_data['current_index'] += 1
            session['input_study_session'] = session_data
            
            return jsonify({
                'is_correct': is_correct,
                'correct_answer': current_question['correct_answer'],
                'explanation': current_question['explanation'],
                'is_complete': session_data['current_index'] >= len(session_data['questions'])
            })
            
        elif study_type == 'choice':
            session_data = session.get('choice_study_session')
            if not session_data:
                return jsonify({'error': 'セッションが見つかりません'}), 400
            
            current_question = session_data['questions'][session_data['current_index']]
            
            # 正解判定
            is_correct = answer == current_question['correct_answer']
            
            # 学習ログを記録
            log_study_result(session_data['session_id'], question_id, answer, 
                           current_question['correct_answer'], is_correct, 'choice')
            
            # セッションを更新
            if is_correct:
                session_data['correct_count'] += 1
            session_data['current_index'] += 1
            session['choice_study_session'] = session_data
            
            return jsonify({
                'is_correct': is_correct,
                'correct_answer': current_question['correct_answer'],
                'explanation': current_question['explanation'],
                'is_complete': session_data['current_index'] >= len(session_data['questions'])
            })
        
        else:
            return jsonify({'error': '無効な学習形式です'}), 400
            
    except Exception as e:
        current_app.logger.error(f"回答提出エラー: {e}")
        return jsonify({'error': 'エラーが発生しました'}), 500

def check_input_answer(user_answer, correct_answer, acceptable_answers):
    """入力問題の正解判定"""
    if user_answer.lower() == correct_answer.lower():
        return True
    
    if acceptable_answers:
        import json
        try:
            acceptable_list = json.loads(acceptable_answers)
            for acceptable in acceptable_list:
                if user_answer.lower() == acceptable.lower():
                    return True
        except:
            pass
    
    return False

def log_study_result(session_id, question_id, user_answer, correct_answer, is_correct, study_type):
    """学習結果をログに記録"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO study_logs (session_id, question_id, user_answer, correct_answer, is_correct, study_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (session_id, question_id, user_answer, correct_answer, is_correct, study_type))
                conn.commit()
    except Exception as e:
        current_app.logger.error(f"学習ログ記録エラー: {e}")

@study_bp.route('/complete_study/<int:session_id>')
@login_required
def complete_study(session_id):
    """学習完了画面"""
    try:
        user_id = str(current_user.id)
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # セッション情報を取得
                cur.execute('''
                    SELECT ss.*, t.name as textbook_name, t.subject
                    FROM study_sessions ss
                    JOIN textbooks t ON ss.textbook_id = t.id
                    WHERE ss.id = ? AND ss.user_id = ?
                ''', (session_id, user_id))
                session_info = cur.fetchone()
                
                if not session_info:
                    flash('学習セッションが見つかりません', 'error')
                    return redirect(url_for('study.dashboard'))
                
                # 学習結果を取得
                cur.execute('''
                    SELECT COUNT(*) as total_questions,
                           COUNT(CASE WHEN is_correct THEN 1 END) as correct_answers
                    FROM study_logs
                    WHERE session_id = ?
                ''', (session_id,))
                result = cur.fetchone()
                
                # セッションを完了に更新
                cur.execute('''
                    UPDATE study_sessions 
                    SET completed = TRUE, completed_at = CURRENT_TIMESTAMP, progress = 1.0
                    WHERE id = ?
                ''', (session_id,))
                conn.commit()
                
                # セッション情報をクリア
                session.pop('input_study_session', None)
                session.pop('choice_study_session', None)
                
                return render_template('study/complete.html',
                                     textbook_name=session_info['textbook_name'],
                                     subject=session_info['subject'],
                                     study_type=session_info['study_type'],
                                     total_questions=result['total_questions'],
                                     correct_answers=result['correct_answers'])
                
    except Exception as e:
        current_app.logger.error(f"学習完了画面エラー: {e}")
        flash('エラーが発生しました', 'error')
        return redirect(url_for('study.dashboard'))

@study_bp.route('/set_page_range_and_prepare/<source>', methods=['POST'])
@login_required
def set_page_range_and_prepare(source):
    """ダッシュボードからの設定保存＆準備画面遷移（学習開始後は変更不可）"""
    user_id = str(current_user.id)
    
    # 学習履歴があるかチェック
    if has_study_history(user_id, source):
        flash("⚠️ 学習開始後は設定変更できません。現在の設定で学習を継続してください。")
        return redirect(url_for('study.prepare', source=source))
    
    page_range = request.form.get('page_range', '').strip()
    difficulty_list = request.form.getlist('difficulty')
    difficulty = ','.join(difficulty_list) if difficulty_list else ''
    
    # デバッグ用ログ出力
    current_app.logger.info(f"[DEBUG] page_range: '{page_range}', difficulty: '{difficulty}'")
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO user_settings (user_id, source, page_range, difficulty)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (user_id, source)
                    DO UPDATE SET page_range = EXCLUDED.page_range, difficulty = EXCLUDED.difficulty
                ''', (user_id, source, page_range, difficulty))
                conn.commit()
        
        # キャッシュクリア（設定変更時）
        clear_user_cache(user_id, source)
        
        flash("✅ 設定を保存しました。")
    except Exception as e:
        current_app.logger.error(f"user_settings保存エラー: {e}")
        flash("❌ 設定の保存に失敗しました")
    
    return redirect(url_for('study.prepare', source=source))

@study_bp.route('/reset_history/<source>', methods=['POST'])
@login_required
def reset_history(source):
    """学習履歴のリセット"""
    try:
        current_app.logger.info(f"履歴リセット開始: user_id={current_user.id}, source={source}")
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # まず、study_logテーブルの構造を確認
                try:
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'study_log'
                    """)
                    columns = [row[0] for row in cur.fetchall()]
                    current_app.logger.info(f"study_logテーブルのカラム: {columns}")
                    
                    # sourceカラムが存在するかチェック
                    if 'source' in columns:
                        # Delete all study history for the user and source
                        cur.execute("""
                            DELETE FROM study_log 
                            WHERE user_id = ? AND source = ?
                        """, (current_user.id, source))
                        deleted_study_logs = cur.rowcount
                        current_app.logger.info(f"削除されたstudy_logレコード数: {deleted_study_logs}")
                    else:
                        current_app.logger.warning("study_logテーブルにsourceカラムが存在しません")
                        # sourceカラムがない場合は、card_idを通じてcardsテーブルからsourceを取得して削除
                        try:
                            cur.execute("""
                                DELETE FROM study_log 
                                WHERE user_id = ? AND card_id IN (
                                    SELECT id FROM cards WHERE source = ?
                                )
                            """, (current_user.id, source))
                            deleted_study_logs = cur.rowcount
                            current_app.logger.info(f"削除されたstudy_logレコード数: {deleted_study_logs}")
                        except Exception as e:
                            current_app.logger.error(f"cardsテーブル経由での削除エラー: {e}")
                            # cardsテーブルも存在しない場合は、全履歴を削除
                            cur.execute("DELETE FROM study_log WHERE user_id = ?", (current_user.id,))
                            deleted_study_logs = cur.rowcount
                            current_app.logger.info(f"全study_logレコード削除数: {deleted_study_logs}")
                    
                    # chunk_progressテーブルからも削除
                    cur.execute("""
                        DELETE FROM chunk_progress 
                        WHERE user_id = ? AND source = ?
                    """, (current_user.id, source))
                    deleted_chunk_progress = cur.rowcount
                    current_app.logger.info(f"削除されたchunk_progressレコード数: {deleted_chunk_progress}")
                    
                    # user_settingsテーブルからも削除
                    cur.execute("""
                        DELETE FROM user_settings 
                        WHERE user_id = ? AND source = ?
                    """, (current_user.id, source))
                    deleted_user_settings = cur.rowcount
                    current_app.logger.info(f"削除されたuser_settingsレコード数: {deleted_user_settings}")
                    
                    conn.commit()
                    
                    # キャッシュクリア
                    clear_user_cache(current_user.id, source)
                    
                    flash(f"✅ 学習履歴をリセットしました（削除レコード数: {deleted_study_logs + deleted_chunk_progress + deleted_user_settings}）")
                    current_app.logger.info(f"履歴リセット完了: user_id={current_user.id}, source={source}")
                    
                except Exception as e:
                    current_app.logger.error(f"テーブル構造確認エラー: {e}")
                    flash("❌ 学習履歴のリセットに失敗しました")
                    
    except Exception as e:
        current_app.logger.error(f"履歴リセットエラー: {e}")
        flash("❌ 学習履歴のリセットに失敗しました")
    
    return redirect(url_for('study.prepare', source=source))

@study_bp.route('/prepare/<source>')
@login_required
def prepare(source):
    """学習準備画面"""
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザー設定を取得
                cur.execute('''
                    SELECT page_range, difficulty FROM user_settings 
                    WHERE user_id = ? AND source = ?
                ''', (user_id, source))
                settings = cur.fetchone()
                
                page_range = settings[0] if settings else ''
                difficulty = settings[1] if settings else ''
                
                # 学習履歴があるかチェック
                has_history = has_study_history(user_id, source)
                
                # 進捗状況を取得
                if has_history:
                    progress = get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty)
                else:
                    progress = create_fallback_stage_info(source, page_range, difficulty, user_id)
                
                return render_template('prepare.html', 
                                     source=source, 
                                     page_range=page_range, 
                                     difficulty=difficulty,
                                     has_history=has_history,
                                     progress=progress)
                                     
    except Exception as e:
        current_app.logger.error(f"学習準備画面エラー: {e}")
        flash("学習準備画面の読み込みに失敗しました")
        return redirect(url_for('admin.admin'))

@study_bp.route('/start_chunk/<source>/<int:stage>/<int:chunk_number>/<mode>')
@login_required
def start_chunk(source, stage, chunk_number, mode):
    """チャンク学習開始"""
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザー設定を取得
                cur.execute('''
                    SELECT page_range, difficulty FROM user_settings 
                    WHERE user_id = ? AND source = ?
                ''', (user_id, source))
                settings = cur.fetchone()
                
                if not settings:
                    flash("❌ 学習設定が見つかりません。準備画面から設定してください。")
                    return redirect(url_for('study.prepare', source=source))
                
                page_range, difficulty = settings
                
                # 学習カードを取得
                cards = get_study_cards_fast(source, stage, mode, page_range, user_id, difficulty, chunk_number)
                
                if not cards:
                    flash("❌ 学習カードが見つかりません。")
                    return redirect(url_for('study.prepare', source=source))
                
                # セッション情報を保存
                session['study_session'] = {
                    'source': source,
                    'stage': stage,
                    'mode': mode,
                    'chunk_number': chunk_number,
                    'page_range': page_range,
                    'difficulty': difficulty,
                    'cards': cards,
                    'current_index': 0,
                    'start_time': current_app.logger.info("学習開始時刻を記録")
                }
                
                return redirect(url_for('study.study', source=source))
                
    except Exception as e:
        current_app.logger.error(f"チャンク学習開始エラー: {e}")
        flash("学習開始に失敗しました")
        return redirect(url_for('study.prepare', source=source))

@study_bp.route('/start_chunk_practice/<source>/<int:chunk_number>')
@login_required
def start_chunk_practice(source, chunk_number):
    """チャンク練習開始"""
    user_id = str(current_user.id)
    
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ユーザー設定を取得
                cur.execute('''
                    SELECT page_range, difficulty FROM user_settings 
                    WHERE user_id = ? AND source = ?
                ''', (user_id, source))
                settings = cur.fetchone()
                
                if not settings:
                    flash("❌ 学習設定が見つかりません。")
                    return redirect(url_for('study.prepare', source=source))
                
                page_range, difficulty = settings
                
                # 練習カードを取得
                cards = get_chunk_practice_cards(user_id, source, 'stage1', chunk_number, page_range, difficulty)
                
                if not cards:
                    flash("❌ 練習カードが見つかりません。")
                    return redirect(url_for('study.prepare', source=source))
                
                # セッション情報を保存
                session['study_session'] = {
                    'source': source,
                    'stage': 'practice',
                    'mode': 'practice',
                    'chunk_number': chunk_number,
                    'page_range': page_range,
                    'difficulty': difficulty,
                    'cards': cards,
                    'current_index': 0
                }
                
                return redirect(url_for('study.study', source=source))
                
    except Exception as e:
        current_app.logger.error(f"チャンク練習開始エラー: {e}")
        flash("練習開始に失敗しました")
        return redirect(url_for('study.prepare', source=source))

@study_bp.route('/study/<source>')
@login_required
def study(source):
    """学習画面"""
    study_session = session.get('study_session')
    
    if not study_session or study_session['source'] != source:
        flash("❌ 学習セッションが見つかりません。")
        return redirect(url_for('study.prepare', source=source))
    
    cards = study_session['cards']
    current_index = study_session['current_index']
    
    if current_index >= len(cards):
        # 学習完了
        return redirect(url_for('study.complete', source=source))
    
    current_card = cards[current_index]
    
    return render_template('study.html', 
                         card=current_card, 
                         current_index=current_index + 1,
                         total_cards=len(cards),
                         source=source)

@study_bp.route('/log_result', methods=['POST'])
def log_result():
    """学習結果の記録"""
    try:
        data = request.get_json()
        card_id = data.get('card_id')
        result = data.get('result')  # 'correct' or 'incorrect'
        answer_time = data.get('answer_time', 0)
        
        if not card_id or not result:
            return jsonify({'error': '必要なデータが不足しています'}), 400
        
        study_session = session.get('study_session')
        if not study_session:
            return jsonify({'error': '学習セッションが見つかりません'}), 400
        
        user_id = current_user.id if current_user.is_authenticated else None
        if not user_id:
            return jsonify({'error': 'ユーザーが認証されていません'}), 401
        
        # 学習結果を記録
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO study_log (user_id, card_id, result, answer_time, stage, mode)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, card_id, result, answer_time, 
                     study_session.get('stage', 'unknown'), 
                     study_session.get('mode', 'unknown')))
                conn.commit()
        
        # セッションの現在インデックスを更新
        study_session['current_index'] += 1
        session['study_session'] = study_session
        
        return jsonify({'success': True, 'next_card': study_session['current_index'] < len(study_session['cards'])})
        
    except Exception as e:
        current_app.logger.error(f"学習結果記録エラー: {e}")
        return jsonify({'error': '学習結果の記録に失敗しました'}), 500

# 学習関連のユーティリティ関数は utils/study_utils.py に移動済み 