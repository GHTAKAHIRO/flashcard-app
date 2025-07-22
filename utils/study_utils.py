"""
学習関連のユーティリティ関数
"""

import math
from functools import wraps
from flask import current_app
from utils.db import get_db_connection, get_db_cursor

def cache_key(*args):
    """キャッシュキーを生成"""
    return ':'.join(str(arg) for arg in args)

def simple_cache(expire_time=180):
    """シンプルなキャッシュデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # キャッシュ機能は後で実装
            return func(*args, **kwargs)
        return wrapper
    return decorator

def clear_user_cache(user_id, source=None):
    """ユーザーキャッシュをクリア"""
    # キャッシュクリア処理（実装は後で追加）
    pass

@simple_cache(expire_time=300)
def has_study_history(user_id, source):
    """指定教材に学習履歴があるかチェック（キャッシュ付き）"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                cur.execute('''
                    SELECT COUNT(*) FROM study_log sl
                    JOIN image i ON sl.card_id = i.id
                    WHERE sl.user_id = ? AND i.source = ?
                ''', (user_id, source))
                count = cur.fetchone()[0]
                return count > 0
    except Exception as e:
        current_app.logger.error(f"学習履歴チェックエラー: {e}")
        return False

def get_chunk_size_by_subject(subject):
    """科目別チャンクサイズを取得"""
    chunk_sizes = {
        'math': 10,
        'english': 15,
        'japanese': 12,
        'science': 8,
        'social': 10
    }
    return chunk_sizes.get(subject, 10)

def get_study_cards_fast(source, stage, mode, page_range, user_id, difficulty='', chunk_number=None):
    """学習カードを高速取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 基本的なカード取得クエリ
                query = '''
                    SELECT id, source, page_number, level, subject, grade, image_path
                    FROM image 
                    WHERE source = ?
                '''
                params = [source]
                
                # ページ範囲フィルタ
                if page_range:
                    # ページ範囲の解析（簡易版）
                    try:
                        if '-' in page_range:
                            start, end = page_range.split('-')
                            query += ' AND page_number BETWEEN ? AND ?'
                            params.extend([int(start), int(end)])
                        else:
                            query += ' AND page_number = ?'
                            params.append(int(page_range))
                    except ValueError:
                        current_app.logger.warning(f"ページ範囲の解析エラー: {page_range}")
                
                # 難易度フィルタ
                if difficulty:
                    difficulty_list = difficulty.split(',')
                    placeholders = ','.join(['?' for _ in difficulty_list])
                    query += f' AND level IN ({placeholders})'
                    params.extend(difficulty_list)
                
                query += ' ORDER BY page_number, level'
                
                cur.execute(query, params)
                cards = cur.fetchall()
                
                # チャンク分割
                if chunk_number and cards:
                    subject = cards[0]['subject'] if hasattr(cards[0], 'subject') else 'math'
                    chunk_size = get_chunk_size_by_subject(subject)
                    start_idx = (chunk_number - 1) * chunk_size
                    end_idx = start_idx + chunk_size
                    cards = cards[start_idx:end_idx]
                
                return cards
                
    except Exception as e:
        current_app.logger.error(f"学習カード取得エラー: {e}")
        return []

def get_chunk_practice_cards(user_id, source, stage, chunk_number, page_range, difficulty):
    """チャンク練習カードを取得"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # 間違えた問題を取得
                cur.execute('''
                    SELECT DISTINCT i.id, i.source, i.page_number, i.level, i.subject, i.grade, i.image_path
                    FROM image i
                    JOIN study_log sl ON i.id = sl.card_id
                    WHERE i.source = ? AND sl.user_id = ? AND sl.result = 'unknown'
                ''', (source, user_id))
                
                wrong_cards = cur.fetchall()
                
                # チャンク分割
                if chunk_number and wrong_cards:
                    subject = wrong_cards[0]['subject'] if hasattr(wrong_cards[0], 'subject') else 'math'
                    chunk_size = get_chunk_size_by_subject(subject)
                    start_idx = (chunk_number - 1) * chunk_size
                    end_idx = start_idx + chunk_size
                    wrong_cards = wrong_cards[start_idx:end_idx]
                
                return wrong_cards
                
    except Exception as e:
        current_app.logger.error(f"練習カード取得エラー: {e}")
        return []

def get_detailed_progress_for_all_stages(user_id, source, page_range, difficulty):
    """全ステージの詳細進捗情報を取得"""
    stages_info = []
    try:
        # ステージ1
        stage1_info = get_stage_detailed_progress(user_id, source, 1, page_range, difficulty)
        if stage1_info:
            stages_info.append(stage1_info)
            if is_stage_perfect(user_id, source, 1, page_range, difficulty):
                return stages_info
        # ステージ2
        stage2_info = get_stage_detailed_progress(user_id, source, 2, page_range, difficulty)
        if stage2_info:
            stages_info.append(stage2_info)
            if is_stage_perfect(user_id, source, 2, page_range, difficulty):
                return stages_info
        # ステージ3
        stage3_info = get_stage_detailed_progress(user_id, source, 3, page_range, difficulty)
        if stage3_info:
            stages_info.append(stage3_info)
        return stages_info
    except Exception as e:
        current_app.logger.error(f"詳細進捗エラー: {e}")
        return []

def create_fallback_stage_info(source, page_range, difficulty, user_id):
    """エラー時のフォールバック：最小限のStage 1情報"""
    try:
        cards = get_study_cards_fast(source, 1, 'test', page_range, user_id, difficulty)
        
        if cards:
            subject = cards[0]['subject'] if hasattr(cards[0], 'subject') else 'math'
            chunk_size = get_chunk_size_by_subject(subject)
            total_chunks = math.ceil(len(cards) / chunk_size)
        else:
            total_chunks = 1
        
        return [{
            'stage': 1,
            'stage_name': 'ステージ 1',
            'total_cards': len(cards) if cards else 0,
            'total_chunks': total_chunks,
            'chunks_progress': [{
                'chunk_number': 1,
                'total_cards': chunk_size if cards else 0,
                'test_completed': False,
                'test_correct': 0,
                'test_wrong': 0,
                'practice_needed': False,
                'practice_completed': False,
                'chunk_completed': False,
                'can_start_test': True,
                'can_start_practice': False
            }],
            'stage_completed': False,
            'can_start': True
        }]
        
    except Exception as e:
        current_app.logger.error(f"フォールバック エラー: {e}")
        return []

def get_stage_detailed_progress(user_id, source, stage, page_range, difficulty):
    """指定ステージの詳細進捗を取得"""
    try:
        # ステージ別の対象カードを取得
        if stage == 1:
            target_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty)
        else:
            # ステージ2・3は簡易実装
            target_cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty)
        
        if not target_cards:
            current_app.logger.debug(f"[STAGE_PROGRESS] Stage{stage}: 対象カードなし")
            return None
        
        subject = target_cards[0]['subject'] if hasattr(target_cards[0], 'subject') else 'math'
        chunk_size = get_chunk_size_by_subject(subject)
        total_chunks = math.ceil(len(target_cards) / chunk_size)
        
        # チャンク進捗を取得
        chunks_progress = []
        for chunk_num in range(1, total_chunks + 1):
            chunk_info = {
                'chunk_number': chunk_num,
                'total_cards': min(chunk_size, len(target_cards) - (chunk_num - 1) * chunk_size),
                'test_completed': False,
                'test_correct': 0,
                'test_wrong': 0,
                'practice_needed': False,
                'practice_completed': False,
                'chunk_completed': False,
                'can_start_test': True,
                'can_start_practice': False
            }
            chunks_progress.append(chunk_info)
        
        return {
            'stage': stage,
            'stage_name': f'ステージ {stage}',
            'total_cards': len(target_cards),
            'total_chunks': total_chunks,
            'chunks_progress': chunks_progress,
            'stage_completed': False,
            'can_start': True
        }
        
    except Exception as e:
        current_app.logger.error(f"ステージ詳細進捗エラー: {e}")
        return None

def is_stage_perfect(user_id, source, stage, page_range, difficulty):
    """指定ステージが全問正解かチェック"""
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cur:
                # ステージの全カードを取得
                cards = get_study_cards_fast(source, stage, 'test', page_range, user_id, difficulty)
                if not cards:
                    return False
                
                # 各カードの正解状況をチェック
                for card in cards:
                    cur.execute('''
                        SELECT COUNT(*) FROM study_log 
                        WHERE user_id = ? AND card_id = ? AND result = 'known'
                    ''', (user_id, card['id']))
                    correct_count = cur.fetchone()[0]
                    
                    if correct_count == 0:
                        return False
                
                return True
                
    except Exception as e:
        current_app.logger.error(f"ステージ完璧判定エラー: {e}")
        return False 