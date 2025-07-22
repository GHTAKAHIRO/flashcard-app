"""
語彙関連のユーティリティ関数
"""

import re
from datetime import datetime
from flask import current_app
from utils.db import get_db_connection, get_db_cursor

def get_vocabulary_chunk_progress(user_id, source, chapter_id, chunk_number):
    """英単語チャンクの進捗状況を取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 基本の進捗情報を取得
                cur.execute('''
                    SELECT is_completed, is_passed, completed_at, passed_at
                    FROM vocabulary_chunk_progress
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                # 正解数を取得
                cur.execute('''
                    SELECT COUNT(*) as correct_count
                    FROM vocabulary_study_log
                    WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ? AND result = 'known'
                ''', (user_id, source, chapter_id, chunk_number))
                correct_result = cur.fetchone()
                correct_count = correct_result[0] if correct_result else 0
                
                if result:
                    result = dict(result)
                    result['correct_count'] = correct_count
                
                return result
    except Exception as e:
        current_app.logger.error(f"英単語チャンク進捗取得エラー: {e}")
        return None

def update_vocabulary_chunk_progress(user_id, source, chapter_id, chunk_number, is_completed=False, is_passed=False):
    """英単語チャンクの進捗状況を更新"""
    try:
        current_app.logger.info(f"進捗更新開始: user={user_id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, completed={is_completed}, passed={is_passed}")
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 既存のレコードがあるかチェック
                cur.execute('''
                    SELECT id FROM vocabulary_chunk_progress
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
                        update_fields.append("is_completed = ?")
                        update_fields.append("completed_at = ?")
                        params.extend([True, now])
                    
                    if is_passed:
                        update_fields.append("is_passed = ?")
                        update_fields.append("passed_at = ?")
                        params.extend([True, now])
                    
                    if update_fields:
                        params.extend([user_id, source, chapter_id, chunk_number])
                        query = f'''
                            UPDATE vocabulary_chunk_progress 
                            SET {', '.join(update_fields)}
                            WHERE user_id = ? AND source = ? AND chapter_id = ? AND chunk_number = ?
                        '''
                        cur.execute(query, params)
                        current_app.logger.info(f"進捗更新完了: {len(update_fields)}フィールド")
                else:
                    # 新規レコードを作成
                    cur.execute('''
                        INSERT INTO vocabulary_chunk_progress 
                        (user_id, source, chapter_id, chunk_number, is_completed, is_passed, completed_at, passed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, source, chapter_id, chunk_number,
                        is_completed, is_passed,
                        now if is_completed else None,
                        now if is_passed else None
                    ))
                    current_app.logger.info("新規進捗レコード作成完了")
                
                conn.commit()
                current_app.logger.info(f"進捗更新完了: user_id={user_id}, source={source}, chapter={chapter_id}, chunk={chunk_number}")
                
    except Exception as e:
        current_app.logger.error(f"進捗更新エラー: {e}")
        raise

def normalize_answer(answer):
    """回答を正規化"""
    if not answer:
        return ""
    
    # 小文字に変換
    normalized = answer.lower()
    
    # 余分な空白を削除
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # 句読点を削除
    normalized = re.sub(r'[、。，．]', '', normalized)
    
    # 括弧とその中身を削除
    normalized = re.sub(r'[（(].*?[）)]', '', normalized)
    
    return normalized

def check_answer(user_answer, correct_answer, acceptable_answers=None):
    """回答をチェック"""
    normalized_user = normalize_answer(user_answer)
    normalized_correct = normalize_answer(correct_answer)
    
    # 完全一致
    if normalized_user == normalized_correct:
        return True, 1.0
    
    # 許容回答がある場合
    if acceptable_answers:
        for acceptable in acceptable_answers:
            normalized_acceptable = normalize_answer(acceptable)
            if normalized_user == normalized_acceptable:
                return True, 1.0
    
    # 類似度を計算
    similarity = calculate_similarity(normalized_user, normalized_correct)
    
    # 80%以上の類似度で正解とする
    return similarity >= 0.8, similarity

def calculate_similarity(str1, str2):
    """文字列の類似度を計算（レーベンシュタイン距離ベース）"""
    if not str1 or not str2:
        return 0.0
    
    # レーベンシュタイン距離を計算
    distance = levenshtein_distance(str1, str2)
    
    # 類似度を計算（距離が小さいほど類似度が高い）
    max_length = max(len(str1), len(str2))
    if max_length == 0:
        return 1.0
    
    similarity = 1.0 - (distance / max_length)
    return max(0.0, similarity)

def levenshtein_distance(str1, str2):
    """レーベンシュタイン距離を計算"""
    len1, len2 = len(str1), len(str2)
    
    # 動的計画法で距離を計算
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    
    # 初期化
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j
    
    # 距離を計算
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if str1[i-1] == str2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
    
    return dp[len1][len2] 