# 社会科一問一答アプリ

地理・歴史・公民の知識を楽しく学べる入力形式のクイズアプリです。

## 特徴

- **入力形式の回答**: キーボードで答えを入力
- **柔軟な採点**: 部分一致やキーワードマッチングで採点
- **学習進捗管理**: 正答率や学習履歴を記録
- **科目別学習**: 地理・歴史・公民の3科目に対応
- **管理者機能**: 問題の追加・編集・削除が可能
- **画像管理**: 問題に関連する画像のアップロード・管理
- **一括画像パス更新**: 単元の画像パス変更時に問題の画像パスも一括更新

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
- **画像管理**: 問題に関連する画像のアップロード・管理
- **一括画像パス更新**: 単元の画像パス変更時に問題の画像パスも一括更新

## 採点システム

### 完全一致
- 正解と完全に一致する場合

### 許容回答
- 複数の正解や表記ゆれを設定可能
- 例: 「東京」「東京都」「Tokyo」をすべて正解として設定

### 部分一致
- キーワードの70%以上が一致する場合
- 例: 「徳川家康」→「徳川家康公」も正解として判定

## 画像管理機能

### 画像のアップロード
- 問題に関連する画像をWasabiストレージにアップロード
- 単元の章番号に基づいて自動的にフォルダが作成される

### 一括画像パス更新
1. 単元管理画面で「画像パス設定」ボタンをクリック
2. 新しい画像URLを入力
3. 「この単元に登録されている問題の画像パスも一括で更新する」にチェック
4. 「更新」ボタンをクリック

**注意**: この操作により、単元の全問題の画像URLが新しいパスに更新されます。画像ファイル名は保持されます。

### 画像パス更新の仕組み
- 古いURL: `https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/old/path/1.jpg`
- 新しいURL: `https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/new/path`
- 更新後: `https://s3.ap-northeast-1-ntt.wasabisys.com/so-image/new/path/1.jpg`

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
├── create_social_studies_tables.py  # 社会科機能用テーブル作成
├── requirements.txt       # Python依存関係
├── test_image_path_update.py  # 画像パス更新機能テスト
├── templates/            # HTMLテンプレート
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── quiz.html
│   ├── admin.html
│   ├── admin_questions.html
│   ├── add_question.html
│   └── social_studies/   # 社会科機能用テンプレート
│       ├── admin_unit_questions.html
│       ├── add_question.html
│       └── edit_question.html
└── README.md
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

バグ報告や機能要望は、GitHubのIssuesでお知らせください。 