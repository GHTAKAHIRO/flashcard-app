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
                # 基本の進捗情報を取得（新しいスキーマではchoice_questionsに進捗情報はないため、study_logから取得）
                cur.execute('''
                    SELECT COUNT(*) as total_attempts,
                           COUNT(CASE WHEN is_correct THEN 1 END) as correct_attempts
                    FROM choice_study_log l
                    JOIN choice_questions q ON l.question_id = q.id
                    JOIN choice_units u ON q.unit_id = u.id
                    JOIN choice_textbooks t ON u.textbook_id = t.id
                    WHERE l.user_id = ? AND t.source = ? AND u.id = ? AND u.unit_number = ?
                ''', (user_id, source, chapter_id, chunk_number))
                result = cur.fetchone()
                
                if result:
                    result = dict(result)
                    result['is_completed'] = result['total_attempts'] > 0
                    result['is_passed'] = result['correct_attempts'] > 0
                
                return result
    except Exception as e:
        current_app.logger.error(f"英単語チャンク進捗取得エラー: {e}")
        return None

def update_vocabulary_chunk_progress(user_id, source, chapter_id, chunk_number, is_completed=False, is_passed=False):
    """英単語チャンクの進捗状況を更新（新しいスキーマではstudy_logで管理）"""
    try:
        current_app.logger.info(f"進捗更新開始: user={user_id}, source={source}, chapter={chapter_id}, chunk={chunk_number}, completed={is_completed}, passed={is_passed}")
        
        # 新しいスキーマでは進捗はstudy_logで管理されるため、この関数は不要
        # 実際の進捗更新はstudy_logへの記録で行われる
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