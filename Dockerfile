# マルチステージビルドでビルド時間を短縮
FROM python:3.11-slim as builder

# ビルド依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境を作成
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 本番用イメージ
FROM python:3.11-slim

# セキュリティとパフォーマンスのための設定
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

# 仮想環境をコピー
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# アプリケーションディレクトリを設定
WORKDIR /app

# アプリケーションコードをコピー
COPY . .

# 権限を設定
RUN chown -R app:app /app
USER app

# ポートを公開
EXPOSE 10000

# アプリケーションを起動
CMD ["python", "app.py"] 