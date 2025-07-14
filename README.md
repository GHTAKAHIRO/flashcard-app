# 社会科一問一答アプリ

地理・歴史・公民の知識を楽しく学べる入力形式のクイズアプリです。

## 特徴

- **入力形式の回答**: キーボードで答えを入力
- **柔軟な採点**: 部分一致やキーワードマッチングで採点
- **学習進捗管理**: 正答率や学習履歴を記録
- **科目別学習**: 地理・歴史・公民の3科目に対応
- **管理者機能**: 問題の追加・編集・削除が可能

## セットアップ

### 1. 必要な環境

- Python 3.8以上
- PostgreSQL
- pip

### 2. データベースの準備

PostgreSQLでデータベースを作成します：

```sql
CREATE DATABASE social_studies_quiz;
```

### 3. 環境変数の設定

`env_example.txt`を参考に、`.env`ファイルを作成してください：

```bash
# データベース設定
DB_HOST=localhost
DB_PORT=5432
DB_NAME=social_studies_quiz
DB_USER=postgres
DB_PASSWORD=your_password_here

# Flask設定
SECRET_KEY=your_secret_key_here
```

### 4. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 5. データベーステーブルの作成

```bash
python create_tables.py
```

### 6. アプリケーションの起動

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスしてください。

## 使用方法

### 一般ユーザー

1. **新規登録**: アカウントを作成
2. **ログイン**: ユーザー名とパスワードでログイン
3. **科目選択**: 地理・歴史・公民から学習したい科目を選択
4. **クイズ開始**: 問題を読んで答えを入力
5. **結果確認**: 正解・不正解と解説を確認

### 管理者

- **デフォルトアカウント**: admin / admin123
- **問題管理**: 新しい問題の追加や既存問題の編集
- **統計確認**: ユーザーの学習状況を確認

## 採点システム

### 完全一致
- 正解と完全に一致する場合

### 許容回答
- 複数の正解や表記ゆれを設定可能
- 例: 「東京」「東京都」「Tokyo」をすべて正解として設定

### 部分一致
- キーワードの70%以上が一致する場合
- 例: 「徳川家康」→「徳川家康公」も正解として判定

## 技術仕様

- **バックエンド**: Flask (Python)
- **データベース**: PostgreSQL
- **フロントエンド**: Bootstrap 5, JavaScript
- **認証**: Flask-Login

## ファイル構成

```
social_studies_quiz_app/
├── app.py                 # メインアプリケーション
├── create_tables.py       # データベーステーブル作成
├── requirements.txt       # Python依存関係
├── templates/            # HTMLテンプレート
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── quiz.html
│   ├── admin.html
│   ├── admin_questions.html
│   └── add_question.html
└── README.md
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

バグ報告や機能要望は、GitHubのIssuesでお知らせください。 