from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from datetime import datetime
import re
from utils.db import get_db_connection, get_db_cursor

choice_studies_bp = Blueprint('choice_studies', __name__)

# ========== 選択問題関連のユーティリティ関数 ==========

def get_choice_chunk_progress(user_id, source, chapter_id, chunk_number):
    """選択問題チャンクの進捗状況を取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 基本の進捗情報を取得
                cur.execute('''
                    SELECT is_completed, is_passed, completed_at, passed_at
                    FROM choice_questions
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                # 正解数を取得
                cur.execute('''
                    SELECT COUNT(*) as correct_count
                    FROM choice_study_log
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ? AND is_correct = 1
                ''', (user_id, source, chapter_id, chunk_number))
                correct_result = cur.fetchone()
                correct_count = correct_result[0] if correct_result else 0
                
                if result:
                    result = dict(result)
                    result['correct_count'] = correct_count
                
                return result
    except Exception as e:
        current_app.logger.error(f"選択問題チャンク進捗取得エラー: {e}")
        return None

def update_choice_chunk_progress(user_id, source, chapter_id, chunk_number, is_completed=False, is_passed=False):
    """選択問題チャンクの進捗状況を更新"""
    try:
        current_app.logger.info(f"進捗更新開始: user={user_id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, completed={is_completed}, passed={is_passed}")
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 既存のレコードがあるかチェック
                cur.execute('''
                    SELECT id FROM choice_questions
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                ''', (user_id, source, chapter_id, chunk_number))
                
                existing = cur.fetchone()
                now = datetime.now()
                
                current_app.logger.info(f"既存レコード: {existing}")
                
                if existing:
                    # 既存レコードを更新
                    update_fields = []
                    params = []
                    
                    if is_completed:
                        update_fields.append("is_completed = TRUE")
                        update_fields.append("completed_at = ?")
                        params.append(now)
                    
                    if is_passed:
                        update_fields.append("is_passed = TRUE")
                        update_fields.append("passed_at = ?")
                        params.append(now)
                    
                    if update_fields:
                        update_fields.append("updated_at = ?")
                        params.append(now)
                        params.extend([user_id, source, chapter_id, chunk_number])
                        
                        update_sql = f'''
                            UPDATE choice_questions
                            SET {', '.join(update_fields)}
                            WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                        '''
                        current_app.logger.info(f"更新SQL: {update_sql}")
                        current_app.logger.info(f"更新パラメータ: {params}")
                        
                        cur.execute(update_sql, params)
                else:
                    # 新規レコードを作成
                    insert_sql = '''
                        INSERT INTO choice_questions 
                        (user_id, source, chapter_id, chunk_number, is_completed, is_passed, completed_at, passed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                    insert_params = (
                        user_id, source, chapter_id, chunk_number,
                        is_completed, is_passed,
                        now if is_completed else None,
                        now if is_passed else None
                    )
                    current_app.logger.info(f"挿入SQL: {insert_sql}")
                    current_app.logger.info(f"挿入パラメータ: {insert_params}")
                    
                    cur.execute(insert_sql, insert_params)
                
                conn.commit()
                current_app.logger.info(f"進捗更新完了: 成功")
                return True
                
    except Exception as e:
        current_app.logger.error(f"選択問題チャンク進捗更新エラー: {e}")
        current_app.logger.error(f"エラー詳細: {str(e)}")
        return False

def normalize_answer(answer):
    """回答を正規化（空白除去、全角→半角変換など）"""
    if not answer:
        return ""
    
    # 空白を除去（日本語の場合は小文字化しない）
    normalized = re.sub(r'\s+', '', answer)
    
    # 全角数字を半角に変換
    normalized = normalized.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    
    # 全角英字を半角に変換
    fullwidth_chars = 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    halfwidth_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    normalized = normalized.translate(str.maketrans(fullwidth_chars, halfwidth_chars))
    
    # 全角記号を半角に変換
    fullwidth_symbols = '！＠＃＄％＾＆＊（）＿＋－＝｛｝｜：；＂＇＜＞？、。・～'
    halfwidth_symbols = '!@#$%^&*()_+-={}|:;"\'<>?,./~'
    normalized = normalized.translate(str.maketrans(fullwidth_symbols, halfwidth_symbols))
    
    # 全角スペースを半角スペースに変換
    normalized = normalized.replace('　', ' ')
    
    # 連続するスペースを単一のスペースに変換
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # 前後のスペースを除去
    normalized = normalized.strip()
    
    return normalized

def check_answer(user_answer, correct_answer, acceptable_answers=None):
    """回答をチェックする"""
    user_norm = normalize_answer(user_answer)
    correct_norm = normalize_answer(correct_answer)
    
    current_app.logger.info(f"採点: ユーザー回答='{user_answer}' -> 正規化='{user_norm}', 正解='{correct_answer}' -> 正規化='{correct_norm}'")
    
    # 完全一致
    if user_norm == correct_norm:
        current_app.logger.info("完全一致で正解")
        return True, "完全一致"
    
    # 許容回答のチェック
    if acceptable_answers:
        current_app.logger.info(f"許容回答チェック: {acceptable_answers}")
        for acceptable in acceptable_answers:
            acceptable_norm = normalize_answer(acceptable)
            current_app.logger.info(f"許容回答比較: '{acceptable}' -> '{acceptable_norm}' vs '{user_norm}'")
            if user_norm == acceptable_norm:
                current_app.logger.info("許容回答で正解")
                return True, "許容回答"
    
    # 数字のみの場合は数値として比較
    if user_norm.isdigit() and correct_norm.isdigit():
        if int(user_norm) == int(correct_norm):
            return True, "数値一致"
    
    # 部分一致（キーワードチェック）
    correct_words = set(correct_norm.split())
    user_words = set(user_norm.split())
    
    if len(correct_words) > 0:
        match_ratio = len(correct_words.intersection(user_words)) / len(correct_words)
        if match_ratio >= 0.7:  # 70%以上のキーワードが一致
            return True, f"部分一致 ({match_ratio:.1%})"
    
    # 文字列の類似度チェック（編集距離ベース）
    if len(correct_norm) > 0:
        similarity = calculate_similarity(user_norm, correct_norm)
        if similarity >= 0.8:  # 80%以上の類似度
            return True, f"類似一致 ({similarity:.1%})"
    
    return False, "不正解"

def calculate_similarity(str1, str2):
    """文字列の類似度を計算（編集距離ベース）"""
    if not str1 or not str2:
        return 0.0
    
    # 短い方の文字列を基準にする
    if len(str1) > len(str2):
        str1, str2 = str2, str1
    
    # 編集距離を計算
    distance = levenshtein_distance(str1, str2)
    max_len = max(len(str1), len(str2))
    
    if max_len == 0:
        return 1.0
    
    return 1.0 - (distance / max_len)

def levenshtein_distance(str1, str2):
    """レーベンシュタイン距離を計算"""
    if len(str1) < len(str2):
        return levenshtein_distance(str2, str1)
    
    if len(str2) == 0:
        return len(str1)
    
    previous_row = list(range(len(str2) + 1))
    for i, c1 in enumerate(str1):
        current_row = [i + 1]
        for j, c2 in enumerate(str2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

# ========== 選択問題関連のルート ==========

@choice_studies_bp.route('/choice_studies')
@login_required
def choice_studies_home():
    """選択問題学習のホーム画面"""
    try:
        # ユーザーの学習履歴を取得（choice_study_logテーブルから）
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT DISTINCT t.source, COUNT(*) as total_words,
                        COUNT(CASE WHEN l.is_correct THEN 1 END) as known_words
                    FROM choice_study_log l
                    JOIN choice_questions q ON l.question_id = q.id
                    JOIN choice_units u ON q.unit_id = u.id
                    JOIN choice_textbooks t ON u.textbook_id = t.id
                    WHERE l.user_id = ?
                    GROUP BY t.source
                ''', (str(current_user.id),))
                vocabulary_sources = cur.fetchall()
        
        # 各セットの総単語数も取得
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT t.source, COUNT(*) as total_available
                    FROM choice_questions q
                    JOIN choice_units u ON q.unit_id = u.id
                    JOIN choice_textbooks t ON u.textbook_id = t.id
                    GROUP BY t.source
                ''')
                total_available = {row[0]: row[1] for row in cur.fetchall()}
        
        # 結果をマージ
        for source in vocabulary_sources:
            source = list(source)  # タプルをリストに変換
            source.append(total_available.get(source[0], 0))  # total_availableを追加
        
        return render_template('choice_studies/home.html', vocabulary_sources=vocabulary_sources)
    except Exception as e:
        current_app.logger.error(f"選択問題ホーム画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('admin.admin'))

@choice_studies_bp.route('/choice_studies/chapters/<source>')
@login_required
def choice_studies_chapters(source):
    """選択問題章選択画面"""
    try:
        # ソースタイトルの設定
        source_titles = {
            'basic': '基本英単語帳',
            'toeic': 'TOEIC単語帳',
            'university': '大学受験単語帳'
        }
        source_title = source_titles.get(source, source)
        
        # 章データを取得（仮の実装 - 後でデータベースから取得）
        chapters = [
            {
                'id': 1,
                'title': 'Chapter 1: 基本単語',
                'description': '日常生活でよく使われる基本単語',
                'total_words': 100,
                'chunk_count': 5
            },
            {
                'id': 2,
                'title': 'Chapter 2: 動詞',
                'description': '重要な動詞の学習',
                'total_words': 80,
                'chunk_count': 4
            },
            {
                'id': 3,
                'title': 'Chapter 3: 形容詞',
                'description': '形容詞の学習',
                'total_words': 60,
                'chunk_count': 3
            }
        ]
        
        return render_template('choice_studies/chapters.html',
                             source=source,
                             source_title=source_title,
                             chapters=chapters)
        
    except Exception as e:
        current_app.logger.error(f"選択問題章選択エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/chunks/<source>/<int:chapter_id>')
@login_required
def choice_studies_chunks(source, chapter_id):
    """選択問題チャンク選択画面"""
    try:
        # ソースタイトルの設定
        source_titles = {
            'basic': '基本英単語帳',
            'toeic': 'TOEIC単語帳',
            'university': '大学受験単語帳'
        }
        source_title = source_titles.get(source, source)
        
        # 章タイトルの設定
        chapter_titles = {
            1: 'Chapter 1: 基本単語',
            2: 'Chapter 2: 動詞',
            3: 'Chapter 3: 形容詞'
        }
        chapter_title = chapter_titles.get(chapter_id, f'Chapter {chapter_id}')
        
        # チャンクデータを取得（仮の実装）
        chunks = []
        for i in range(1, 6):  # 5つのチャンク
            progress = get_choice_chunk_progress(current_user.id, source, chapter_id, i)
            chunks.append({
                'number': i,
                'title': f'Chunk {i}',
                'word_count': 20,
                'is_completed': progress['is_completed'] if progress else False,
                'is_passed': progress['is_passed'] if progress else False,
                'correct_count': progress.get('correct_count', 0) if progress else 0
            })
        
        return render_template('choice_studies/chunks.html',
                             source=source,
                             source_title=source_title,
                             chapter_id=chapter_id,
                             chapter_title=chapter_title,
                             chunks=chunks)
        
    except Exception as e:
        current_app.logger.error(f"選択問題チャンク選択エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_chapters', source=source))

@choice_studies_bp.route('/choice_studies/start/<source>/<int:chapter_id>/<int:chunk_number>')
@choice_studies_bp.route('/choice_studies/start/<source>/<int:chapter_id>/<int:chunk_number>/<mode>')
@login_required
def choice_studies_start(source, chapter_id, chunk_number, mode=None):
    """選択問題学習開始"""
    try:
        # デフォルトモードを設定
        if mode is None:
            mode = 'test'
        
        # 学習セッション情報をセッションに保存
        session['vocabulary_session'] = {
            'source': source,
            'chapter_id': chapter_id,
            'chunk_number': chunk_number,
            'mode': mode,
            'current_word_index': 0,
            'total_words': 0,
            'correct_count': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # 単語データを取得
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT q.id, q.question, q.correct_answer, q.choices
                    FROM choice_questions q
                    JOIN choice_units u ON q.unit_id = u.id
                    JOIN choice_textbooks t ON u.textbook_id = t.id
                    WHERE t.source = ? AND u.chapter_id = ? AND q.chunk_number = ?
                    ORDER BY q.id
                ''', (source, chapter_id, chunk_number))
                words = cur.fetchall()
        
        if not words:
            flash("問題が見つかりませんでした")
            return redirect(url_for('choice_studies.choice_studies_chunks', source=source, chapter_id=chapter_id))
        
        # セッション情報を更新
        session['vocabulary_session']['total_words'] = len(words)
        session['vocabulary_session']['words'] = [
            {
                'id': word[0],
                'question': word[1],
                'correct_answer': word[2],
                'choices': word[3]
            }
            for word in words
        ]
        
        return redirect(url_for('choice_studies.choice_studies_study', source=source))
        
    except Exception as e:
        current_app.logger.error(f"選択問題学習開始エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_chunks', source=source, chapter_id=chapter_id))

@choice_studies_bp.route('/choice_studies/study/<source>')
@login_required
def choice_studies_study(source):
    """選択問題学習画面"""
    try:
        # セッション情報を取得
        session_data = session.get('vocabulary_session')
        if not session_data or session_data['source'] != source:
            flash("学習セッションが見つかりません")
            return redirect(url_for('choice_studies.choice_studies_home'))
        
        current_index = session_data['current_word_index']
        words = session_data['words']
        
        if current_index >= len(words):
            # 学習完了
            return redirect(url_for('choice_studies.choice_studies_complete'))
        
        current_word = words[current_index]
        
        return render_template('choice_studies/study.html',
                             source=source,
                             word=current_word,
                             current_index=current_index + 1,
                             total_words=len(words),
                             mode=session_data['mode'])
        
    except Exception as e:
        current_app.logger.error(f"選択問題学習画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/answer', methods=['POST'])
@login_required
def choice_studies_answer():
    """選択問題回答処理"""
    try:
        # セッション情報を取得
        session_data = session.get('vocabulary_session')
        if not session_data:
            flash("学習セッションが見つかりません")
            return redirect(url_for('choice_studies.choice_studies_home'))
        
        user_answer = request.form.get('answer', '').strip()
        current_index = session_data['current_word_index']
        words = session_data['words']
        
        if current_index >= len(words):
            flash("学習が完了しています")
            return redirect(url_for('choice_studies.choice_studies_complete'))
        
        current_word = words[current_index]
        
        # 回答をチェック
        is_correct, result_type = check_answer(user_answer, current_word['correct_answer'])
        
        # 結果をログに記録
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    INSERT INTO choice_study_log
                    (user_id, source, chapter_id, chunk_number, question_id, user_answer, 
                     correct_answer, is_correct, result_type, answered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    current_user.id,
                    session_data['source'],
                    session_data['chapter_id'],
                    session_data['chunk_number'],
                    current_word['id'],
                    user_answer,
                    current_word['correct_answer'],
                    is_correct,
                    result_type,
                    datetime.now()
                ))
                conn.commit()
        
        # セッション情報を更新
        if is_correct:
            session_data['correct_count'] += 1
        
        session_data['current_word_index'] += 1
        session['vocabulary_session'] = session_data
        
        # 次の単語へ
        if session_data['current_word_index'] >= len(words):
            return redirect(url_for('choice_studies.choice_studies_complete'))
        else:
            return redirect(url_for('choice_studies.choice_studies_study', source=session_data['source']))
        
    except Exception as e:
        current_app.logger.error(f"選択問題回答処理エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/complete', methods=['POST'])
@login_required
def choice_studies_complete():
    """選択問題学習完了処理"""
    try:
        # セッション情報を取得
        session_data = session.get('vocabulary_session')
        if not session_data:
            flash("学習セッションが見つかりません")
            return redirect(url_for('choice_studies.choice_studies_home'))
        
        # 進捗を更新
        total_words = session_data['total_words']
        correct_count = session_data['correct_count']
        accuracy = (correct_count / total_words * 100) if total_words > 0 else 0
        
        # 完了条件（80%以上で完了、60%以上で合格）
        is_completed = accuracy >= 80
        is_passed = accuracy >= 60
        
        # 進捗をデータベースに保存
        update_choice_chunk_progress(
            current_user.id,
            session_data['source'],
            session_data['chapter_id'],
            session_data['chunk_number'],
            is_completed=is_completed,
            is_passed=is_passed
        )
        
        # セッションをクリア
        session.pop('vocabulary_session', None)
        
        return redirect(url_for('choice_studies.choice_studies_result', source=session_data['source']))
        
    except Exception as e:
        current_app.logger.error(f"選択問題学習完了処理エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/result/<source>')
@login_required
def choice_studies_result(source):
    """選択問題学習結果表示"""
    try:
        # 最近の学習結果を取得
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT chapter_id, chunk_number, COUNT(*) as total_words,
                           COUNT(CASE WHEN is_correct THEN 1 END) as correct_words,
                           MAX(answered_at) as last_studied
                    FROM choice_study_log
                    WHERE user_id = ? AND source = ?
                    GROUP BY chapter_id, chunk_number
                    ORDER BY last_studied DESC
                    LIMIT 10
                ''', (current_user.id, source))
                recent_results = cur.fetchall()
        
        return render_template('choice_studies/result.html',
                             source=source,
                             recent_results=recent_results)
        
    except Exception as e:
        current_app.logger.error(f"選択問題結果表示エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/admin')
@login_required
def choice_studies_admin():
    """選択問題管理画面"""
    try:
        # 管理者権限チェック
        if not current_user.is_admin:
            flash("管理者権限が必要です")
            return redirect(url_for('choice_studies.choice_studies_home'))
        
        # 統計情報を取得
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 総単語数
                cur.execute('SELECT COUNT(*) FROM choice_questions')
                total_words = cur.fetchone()[0]
                
                # 学習された単語数
                cur.execute('SELECT COUNT(DISTINCT question_id) FROM choice_study_log')
                studied_words = cur.fetchone()[0]
                
                # 正解率
                cur.execute('''
                    SELECT COUNT(*) as total_answers,
                           COUNT(CASE WHEN is_correct THEN 1 END) as correct_answers
                    FROM choice_study_log
                ''')
                result = cur.fetchone()
                total_answers = result[0] if result else 0
                correct_answers = result[1] if result else 0
                accuracy = (correct_answers / total_answers * 100) if total_answers > 0 else 0
        
        return render_template('choice_studies/admin.html',
                             total_words=total_words,
                             studied_words=studied_words,
                             total_answers=total_answers,
                             correct_answers=correct_answers,
                             accuracy=accuracy)
        
    except Exception as e:
        current_app.logger.error(f"選択問題管理画面エラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_home'))

@choice_studies_bp.route('/choice_studies/upload', methods=['POST'])
@login_required
def choice_studies_upload():
    """選択問題データアップロード"""
    try:
        # 管理者権限チェック
        if not current_user.is_admin:
            flash("管理者権限が必要です")
            return redirect(url_for('choice_studies.choice_studies_admin'))
        
        # CSVファイルの処理（簡易実装）
        flash("アップロード機能は現在開発中です")
        return redirect(url_for('choice_studies.choice_studies_admin'))
        
    except Exception as e:
        current_app.logger.error(f"選択問題アップロードエラー: {e}")
        flash("エラーが発生しました")
        return redirect(url_for('choice_studies.choice_studies_admin')) 