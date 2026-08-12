# FastAPI + LangChain + LangGraph Template

FastAPI・LangChain・LangGraph・PostgreSQL・Redisを組み合わせた、AIチャットバックエンドの開発テンプレートです。JWT認証基盤とLangGraphによる`User → Gemini → Tavily → 検索結果評価 → Gemini → 最終回答`のワークフローを備えています。

## 技術スタック

| 分類 | 技術 |
| --- | --- |
| 言語 / ランタイム | Python 3.13 |
| Web Framework | FastAPI, Uvicorn |
| AI | LangChain, LangGraph, Gemini (`langchain-google-genai`), Tavily (`langchain-tavily`) |
| DB | PostgreSQL, SQLAlchemy 2.x (async), Alembic |
| Cache / State | Redis |
| 認証 | PyJWT, pwdlib (Argon2) |
| バリデーション | Pydantic v2, pydantic-settings |
| パッケージ管理 | uv |
| テスト | pytest, pytest-asyncio, pytest-mock, pytest-cov, HTTPX |
| Lint / Format | Ruff |
| インフラ | Docker, Docker Compose, Nginx |
| CI/CD | GitHub Actions |

## ディレクトリ構造

```text
project-root/
├── .github/workflows/deploy.yml   # CI (test) + CD (SSH deploy)
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPIエントリーポイント
│   │   ├── api/                   # ルーティング + DI
│   │   ├── core/                  # 設定 / セキュリティ / DB接続
│   │   ├── models/                # SQLAlchemy ORM
│   │   ├── schemas/                # Pydantic Schema
│   │   ├── services/               # ユースケース層
│   │   ├── repositories/           # データアクセス層
│   │   ├── ai/                     # LangChain / LangGraph / Gemini / Tavily
│   │   └── infrastructure/         # Redis / HTTPクライアント
│   ├── alembic/                    # DBマイグレーション
│   ├── tests/{unit,integration,fixtures}/
│   ├── pyproject.toml / uv.lock
│   └── Dockerfile
├── nginx/nginx.conf
├── docker-compose.yml              # 開発環境
├── docker-compose.prod.yml         # 本番環境
├── .env.example                    # docker-compose用
└── backend/.env.example            # ホスト上で直接起動する場合用
```

## 必要な環境

- Python 3.13（`uv`が自動で用意するため手動インストールは不要）
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose（コンテナで動かす場合）

## uvのセットアップ

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

cd backend
uv sync   # pyproject.toml / uv.lock から依存関係を再現
```

## 環境変数

- ルートの `.env.example` … `docker-compose` で使用（Postgres/Redis の認証情報 + バックエンドへ渡す設定）
- `backend/.env.example` … `backend/` 直下で `uv run uvicorn ...` のようにホスト上で直接起動する場合用

いずれも `.env` にコピーして値を埋めてください（`.env` はコミットしないでください）。

| 変数 | 説明 |
| --- | --- |
| `DATABASE_URL` | 例: `postgresql+asyncpg://user:pass@host:5432/app` |
| `REDIS_URL` | 例: `redis://host:6379/0` |
| `JWT_SECRET_KEY` | JWT署名用シークレット（32byte以上推奨） |
| `JWT_ALGORITHM` | 既定 `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token有効期限（分） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token有効期限（日）。RedisにJTI単位で保存されます |
| `GOOGLE_API_KEY` | Gemini用APIキー |
| `TAVILY_API_KEY` | Tavily検索用APIキー |
| `GEMINI_MODEL` | 既定 `gemini-2.5-flash` |
| `DEBUG` | 本番では必ず `false` |

## 開発環境

### Docker Composeで起動

```bash
cp .env.example .env   # 値を編集してから

docker compose up --build
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Nginx経由のヘルスチェック: http://localhost/health

backendコンテナは `backend/` をバインドマウントし、`--reload` 付きUvicornで起動するため、コード変更が即座に反映されます（`.venv` は名前付きボリュームで分離しているためホストの仮想環境と衝突しません）。

### Dockerを使わずホストで直接起動

```bash
cd backend
cp .env.example .env   # localhostのPostgres/Redisを指す値に編集
uv run uvicorn app.main:app --reload
```

## DB Migration

```bash
cd backend
uv run alembic upgrade head          # マイグレーション適用
uv run alembic revision --autogenerate -m "message"   # 新規マイグレーション作成
```

Docker Compose経由で実行する場合:

```bash
docker compose exec backend uv run alembic upgrade head
```

## テスト実行方法

```bash
cd backend
uv run pytest                        # unit tests（既定でintegrationは除外）
uv run pytest -m integration         # PostgreSQL/Redisが起動している状態で結合テスト
uv run pytest --cov=app --cov-report=term-missing   # カバレッジ付き
```

結合テスト (`tests/integration/`) はFastAPI → 実PostgreSQL → 実Redisを実際に使用するため、`docker compose up postgres redis` などで両方を起動した状態で実行してください。Gemini/TavilyはUnit Testでは全てMockに置き換えています（`tests/unit/test_ai_graph_nodes.py`）。

## Ruff実行方法

```bash
cd backend
uv run ruff check .      # Lint
uv run ruff format .     # Format
```

## 本番環境

```bash
cp .env.example .env     # 本番用の値（強固なパスワード・シークレット）を設定
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend uv run alembic upgrade head
```

`docker-compose.prod.yml` では以下を行っています。

- `--reload`を使用しない本番用Uvicorn起動
- backendコンテナのポートをホストに公開せず、Nginxのみを外部公開の入口とする
- PostgreSQL/RedisはDocker内部ネットワークのみに限定し、ポートを公開しない
- PostgreSQLデータは名前付きVolumeで永続化
- HTTPSへ拡張する場合は`nginx/nginx.conf`にTLS用`server`ブロックを追加し、`docker-compose.prod.yml`の`443`ポート・証明書マウントのコメントアウトを外してください

## GitHub Actionsによるデプロイ方法

`.github/workflows/deploy.yml` は `main` へのpushをトリガーに、テスト → SSHでVPSへ接続 → `git pull` → `docker compose build/up` → `alembic upgrade head` を実行します。

以下のSecretsをGitHubリポジトリに登録してください（Settings → Secrets and variables → Actions）。

| Secret名 | 内容 |
| --- | --- |
| `VPS_HOST` | デプロイ先VPSのホスト名 / IPアドレス |
| `VPS_USER` | SSHログインユーザー名 |
| `VPS_SSH_PRIVATE_KEY` | SSH秘密鍵（PEM形式） |
| `VPS_SSH_PORT` | SSHポート番号 |
| `VPS_PROJECT_PATH` | VPS上のリポジトリ配置先パス |

VPS側には事前に以下を用意してください。

1. リポジトリをclone済みであること（`git pull`が実行できる状態）
2. Docker / Docker Composeがインストール済みであること
3. VPS上の `.env`（本番用の値）が配置済みであること（`.env`はGit管理対象外のため、初回は手動で配置）

## 未実装・今後対応が必要な事項

- 認証API（登録・ログイン・リフレッシュ・ログアウト）の基盤は実装済みですが、パスワードリセットやメール確認などの拡張は未実装です
- Redisのレート制限機能は接続基盤のみで、具体的なレート制限ロジックは未実装です
- LangGraphのワークフローは検索要否判定が簡易的なダミー実装です。実運用では`draft_response`内の判定ロジックを強化してください
