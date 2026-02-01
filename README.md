# Hackathon-J-Team-application

Hackathon-J-Team-application
Flask と MySQL を使用した SNS アプリケーションです。

技術スタック
バックエンド: Flask 2.2.2 (Python 3.11)
データベース: MySQL 8.0
コンテナ: Docker / Docker Compose
前提条件
以下がインストールされていることを確認してください：

Docker
Docker Compose
環境構築

1. リポジトリのクローン
   git clone <repository-url>
   cd Hackathon-J-Team-application
2. 環境変数の設定
   プロジェクトのルートディレクトリに .env ファイルを作成し、以下の環境変数を設定してください：

# .env ファイルの作成

cp .env.example .env
または、以下の内容で .env ファイルを新規作成してください：

# MySQL設定

DB_ROOT_PASSWORD=rootpassword
DB_DATABASE=snsapp
DB_USER=testuser
DB_PASSWORD=testuser

# Flask設定

FLASK_PORT=5000
⚠️ 注意: .env ファイルには機密情報が含まれるため、Git にコミットしないでください（.gitignore で除外済み）。

3. Docker コンテナの起動
   docker compose up -d --build
   このコマンドにより、以下の2つのコンテナが起動します：

コンテナ名 説明 ポート
MySQL データベースサーバー 内部のみ
Flask アプリケーションサーバー 5000 4. 動作確認
ブラウザで以下の URL にアクセスしてください：

http://localhost:5000
「Hello World」と表示されれば、環境構築は完了です。

よく使うコマンド
コンテナの操作

# コンテナの起動

docker compose up -d

# コンテナの停止

docker compose down

# コンテナの再起動

docker compose restart

# コンテナのログを確認

docker compose logs -f

# 特定のコンテナのログを確認

docker compose logs -f app
docker compose logs -f db
コンテナ内に入る

# Flask コンテナに入る

docker compose exec app bash

# MySQL コンテナに入る

docker compose exec db bash

# MySQL に直接接続

docker compose exec db mysql -u testuser -ptestuser snsapp
データベースのリセット
データベースを初期状態に戻したい場合：

# コンテナとボリュームを削除

docker compose down -v

# 再度ビルド＆起動

docker compose up -d --build
プロジェクト構成
.
├── Docker/
│ ├── Flask/
│ │ └── Dockerfile # Flask用Dockerfile
│ └── MySQL/
│ ├── Dockerfile # MySQL用Dockerfile
│ ├── init.sql # DB初期化スクリプト
│ └── my.cnf # MySQL設定ファイル
├── SNSApp/
│ └── app.py # Flaskアプリケーション
├── docker-compose.yml # Docker Compose設定
├── requirements.txt # Pythonパッケージ
├── .env # 環境変数（要作成）
└── README.md
データベース構成
初期化時に以下のテーブルが作成されます：

users: ユーザー情報
posts: 投稿情報
comments: コメント情報
トラブルシューティング
ポートが使用中の場合

# 使用中のポートを確認

lsof -i :5000

# .env ファイルの FLASK_PORT を別の番号に変更

FLASK_PORT=5001
コンテナが起動しない場合

# コンテナの状態を確認

docker compose ps

# 詳細なログを確認

docker compose logs
データベース接続エラーの場合
MySQL コンテナのヘルスチェックが完了するまで待ってください（約30秒〜1分）。

# ヘルスチェックの状態を確認

docker compose ps
db コンテナが healthy になっていることを確認してください。
