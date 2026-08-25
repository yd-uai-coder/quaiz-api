# QuAiz API

生成AIでクイズを作って遊べるアプリ「QuAiz」のバックエンドです。FastAPI・LangChain(LangGraph)・PostgreSQL・Redisで構成され、JWT認証基盤とLangGraphによる`カテゴリ/キーワード指定 → Gemini(構造化出力) → バリデーション → (再試行 | 確定)`のクイズ生成ワークフローを備えています。フロントエンドはNext.jsで別プロジェクトとして開発し、本APIはJSONのみを返します(サーバーサイドレンダリングは行いません)。

## 技術スタック

| 分類 | 技術 |
| --- | --- |
| 言語 / ランタイム | Python 3.13 |
| Web Framework | FastAPI, Uvicorn |
| AI | LangChain, LangGraph, Gemini (`langchain-google-genai`) |
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
│   │   ├── models/                # SQLAlchemy ORM (user.py: User/UserCredential, quiz.py: クイズドメイン)
│   │   ├── schemas/                # Pydantic Schema
│   │   ├── services/               # ユースケース層
│   │   ├── repositories/           # データアクセス層
│   │   ├── ai/                     # LangChain / LangGraph / Gemini(クイズ生成ワークフロー)
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
| `GOOGLE_API_KEY` | Gemini用APIキー(クイズ生成に必須) |
| `GEMINI_MODEL` | 既定 `gemini-3.1-flash-lite` |
| `TAVILY_API_KEY` | Tavily検索用APIキー(クイズの回答をWeb検索で裏付けるのに必須) |
| `CORS_ORIGINS` | 許可するフロントエンドのオリジンをJSON配列文字列で指定。例: `["https://example.com"]`。未設定時は `["http://localhost:3000"]`。本番では必ず実際のフロントエンドのオリジンに上書きすること |
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

### Swagger UIへの接続方法

Swagger UIは以下のいずれからでもアクセスできます。

- `http://localhost:8000/docs`（backendコンテナに直接アクセス）
- `http://localhost/docs`（`nginx/nginx.conf`が`/`を丸ごとbackendへプロキシしているため、Nginx経由でも到達できます）

ログインが必要なエンドポイント（クイズ生成・回答送信・管理者用の編集/削除など）を試す場合は、事前にアクセストークンで認証してください。

1. `POST /api/v1/auth/register`（初回のみ）→ `POST /api/v1/auth/login`を「Try it out」で実行し、レスポンスの`access_token`をコピーする
2. 画面右上の「Authorize」ボタンをクリックし、コピーした`access_token`の値だけをそのまま貼り付ける（`HTTPBearer`方式のため`Bearer `プレフィックスは不要）
3. 「Authorize」→「Close」を押すと、以降「鍵アイコン」の付いたエンドポイントにも認証済みでリクエストできる

### pgAdmin(Windows)からPostgresに接続する

`docker-compose.yml`のpostgresサービスは`${POSTGRES_PORT:-5432}:5432`でホストにポート公開しているため、WSL2上で`docker compose up`（またはpostgresのみなら`docker compose up -d postgres`）を起動した状態であれば、Windows側にインストールしたpgAdminからそのまま接続できます（WSL2はWSL内でリッスンしているポートをWindowsの`localhost`へ自動フォワードします）。

pgAdminで「Register > Server」から、`.env`の値を使って以下を入力してください。

| 項目 | 値 |
| --- | --- |
| Host | `localhost` |
| Port | `.env`の`POSTGRES_PORT`（未設定なら`5432`） |
| Maintenance database | `.env`の`POSTGRES_DB` |
| Username | `.env`の`POSTGRES_USER` |
| Password | `.env`の`POSTGRES_PASSWORD` |

`localhost`で繋がらない場合は、WSL側で`hostname -I`（または`ip addr show eth0`）を実行して表示されるIPアドレスをHostに指定してください。

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

## 初期データ投入(シーディング)

`difficulty_levels`(5件)に加え、`categories`(8件: アニメ・ゲーム/美術/観光/スポーツ/政治・経済/音楽/映画/グルメ)と
初期ADMINユーザー(email: `admin@admin.com` / password: `admin0123`)は、マイグレーション
(`943c6a5db794_add_difficulty_levels.py`, `72c54fa6fa45_seed_categories_and_admin_user.py`)内で
`bulk_insert`されるため、`alembic upgrade head`を実行するだけで自動的に投入される
(重複時は`ON CONFLICT DO NOTHING`等でスキップする実装のため、複数回適用しても安全)。
**本番投入後は`admin@admin.com`のパスワードを速やかに変更すること**(平文の初期パスワードがGit履歴に残るため)。

上記に加えて、旧Java/Spring版の設計資料(`GW11月発表資料.pdf`)相当のサンプルデータ(カテゴリ・キーワード・
サンプルユーザー・クイズ)を投入したい場合は、以下のスクリプトを別途実行する。
カテゴリ/キーワード/ユーザーは既存があれば再利用するため複数回実行しても安全。クイズは重複チェックをしないため、
同じクイズを増やしたくない場合は既存データを確認してから実行すること。

```bash
cd backend
PYTHONPATH=. uv run python scripts/seed.py
```

## テスト実行方法

```bash
cd backend
uv run pytest                        # unit tests（既定でintegrationは除外）
uv run pytest -m integration         # PostgreSQL/Redisが起動している状態で結合テスト
uv run pytest --cov=app --cov-report=term-missing   # カバレッジ付き
```

結合テスト (`tests/integration/`) はFastAPI → 実PostgreSQL → 実Redisを実際に使用するため、`docker compose up postgres redis` などで両方を起動した状態で実行してください。Gemini/Tavilyは単体・結合テストいずれも `monkeypatch.setattr(nodes, "get_gemini_llm", ...)` / `monkeypatch.setattr(nodes, "get_tavily_search_tool", ...)` で全てMockに置き換えています（`tests/unit/test_quiz_generation_nodes.py`, `tests/integration/test_quiz_flow.py`）。

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
- カテゴリ・キーワードの新規作成APIはありません。カテゴリは`alembic upgrade head`によるマイグレーション内シードが前提で、管理者用の登録APIは未実装です（キーワードはクイズ生成時に自動でget-or-createされます）
- ADMIN roleへの昇格用APIはありません。管理者にする場合は `authentications.role` を直接更新してください
- クイズ生成は「タイトル・問題文の生成に失敗した/DBカラム長を超える等のバリデーション失敗」を最大3回まで自動リトライし、Gemini/Tavily呼び出し自体の一時的なエラーも最大3回までリトライしますが、それでも失敗した場合はエラーを返すのみで、キューイングや非同期リトライは行いません
