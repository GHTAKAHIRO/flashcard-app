# PostgreSQLデータベース設定ガイド

## 概要
Renderの無料プランでは、SQLiteデータベースは永続化されません。長期的な解決策として、PostgreSQLデータベースを使用することを推奨します。

## 手順

### 1. RenderでPostgreSQLデータベースを作成
1. Renderダッシュボードにログイン
2. 「New」→「PostgreSQL」を選択
3. データベース名を設定（例：`flashcards_db`）
4. リージョンを選択（例：`Oregon (US West)`）
5. プランを選択（無料プラン：`Free`）
6. 「Create Database」をクリック

### 2. 環境変数の設定
データベース作成後、以下の情報が表示されます：
- **Database URL**: `postgresql://username:password@host:port/database`
- **External Database URL**: 外部接続用URL

### 3. render.yamlの更新
```yaml
services:
  - type: web
    name: flashcard-app
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DB_TYPE
        value: postgresql
      - key: DB_HOST
        value: your-postgresql-host
      - key: DB_PORT
        value: 5432
      - key: DB_NAME
        value: your-database-name
      - key: DB_USER
        value: your-username
      - key: DB_PASSWORD
        value: your-password
      - key: FLASK_ENV
        value: production
    healthCheckPath: /
    autoDeploy: true
```

### 4. データベースの初期化
PostgreSQLデータベースが作成されたら、以下の手順で初期化します：

1. アプリケーションをデプロイ
2. 管理画面にアクセス
3. 「初期データ復元」ボタンをクリック

## 注意事項
- 無料プランのPostgreSQLは90日間非アクティブで削除される可能性があります
- 本番環境では有料プランの使用を推奨します
- データベースのバックアップを定期的に取得することを推奨します

## トラブルシューティング
- 接続エラーが発生した場合は、環境変数の設定を確認
- データベースが存在しない場合は、Renderダッシュボードで確認
- 権限エラーが発生した場合は、ユーザー名とパスワードを確認 