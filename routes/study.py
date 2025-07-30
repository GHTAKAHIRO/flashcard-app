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
                for assignment in assignments:
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
                            assignment['unit_details'] = cur.fetchall()
                        except json.JSONDecodeError:
                            assignment['unit_details'] = []
                    else:
                        assignment['unit_details'] = []
                
                return render_template('dashboard.html', assignments=assignments)
                
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
                    SELECT ta.*, 
                           CASE 
                               WHEN ta.assignment_type = 'input' THEN it.name
                               WHEN ta.assignment_type = 'choice' THEN ct.source
                           END as textbook_name
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
                
                # 学習タイプに応じてリダイレクト
                if assignment['assignment_type'] == 'input':
                    return redirect(url_for('input_studies.quiz', textbook_id=assignment['textbook_id']))
                else:
                    return redirect(url_for('choice_studies.choice_studies_home', source=assignment['textbook_name']))
                
    except Exception as e:
        current_app.logger.error(f"学習開始エラー: {e}")
        flash('学習の開始に失敗しました', 'error')
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