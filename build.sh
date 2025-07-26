#!/bin/bash

# ビルド時間短縮のための最適化スクリプト

echo "🚀 ビルド最適化を開始します..."

# キャッシュディレクトリのクリア
echo "📦 キャッシュをクリアしています..."
rm -rf __pycache__
rm -rf .pytest_cache
rm -rf .mypy_cache

# 依存関係のインストール（キャッシュを使用）
echo "📥 依存関係をインストールしています..."
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r requirements.txt

# データベースの初期化（必要な場合のみ）
echo "🗄️ データベースを初期化しています..."
python init_db.py

echo "✅ ビルド最適化が完了しました！" 