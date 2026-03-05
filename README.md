# Gmail メール自動PDF化システム

特定の差出人からの Gmail メールを自動的に PDF 化して保存するシステムです。
手動フェッチとリアルタイム監視（Google Pub/Sub）の両方に対応しています。

## 機能

- 指定した差出人からのメールを自動検出
- メール本文（HTML / プレーンテキスト）を PDF に変換
- 日本語メールに対応（Noto Sans JP 等）
- Pub/Sub によるリアルタイム監視
- 処理済みメールの重複排除

## 前提条件

- Python 3.11 以上
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- Google Cloud Platform アカウント

### macOS: システム依存パッケージ

```bash
brew install pango gdk-pixbuf libffi
```

## セットアップ

### 1. プロジェクトのインストール

```bash
# 仮想環境の構築・有効化
uv venv
source .venv/bin/activate

# パッケージのインストール
uv pip install -e ".[dev]"
```

### 2. GCP プロジェクト設定

1. [GCP コンソール](https://console.cloud.google.com/) でプロジェクトを作成
2. **Gmail API** と **Cloud Pub/Sub API** を有効化
3. 「認証情報」から OAuth クライアント ID を作成（デスクトップアプリケーション）
4. JSON をダウンロードし、`credentials/credentials.json` に配置

```bash
mv ~/Downloads/client_secret_*.json credentials/credentials.json
```

### 3. Pub/Sub 設定（リアルタイム監視を使う場合）

1. Pub/Sub トピック `gmail-notifications` を作成
2. トピックに `gmail-api-push@system.gserviceaccount.com` の Pub/Sub パブリッシャー権限を付与
3. Pull 型サブスクリプション `gmail-notifications-sub` を作成

詳細な手順は [docs/setup.md](docs/setup.md) を参照してください。

### 4. 設定ファイルの準備

```bash
# テンプレート生成
uv run python -m gmail_automation config-init

# config.yaml を編集
# - gmail.target_senders: 監視対象のメールアドレス
# - pubsub.project_id: GCP プロジェクト ID
```

### 5. 初回認証

```bash
uv run python -m gmail_automation auth
```

ブラウザが開き、Google アカウントでの認証を求められます。許可するとトークンが `credentials/token.json` に保存されます。

## 使い方

### 手動フェッチ

過去 N 日分のメールを取得して PDF 化します。

```bash
# 過去 7 日分（デフォルト）
uv run python -m gmail_automation fetch

# 過去 30 日分
uv run python -m gmail_automation fetch --days 30
```

日付範囲を指定して取得することもできます。

```bash
# 2025年1月1日〜2025年12月31日のメールを取得
uv run python -m gmail_automation fetch --after 2025/01/01 --before 2025/12/31

# 開始日のみ指定（2025年4月1日以降のすべてのメール）
uv run python -m gmail_automation fetch --after 2025/04/01

# 終了日のみ指定（2025年6月30日以前のすべてのメール）
uv run python -m gmail_automation fetch --before 2025/06/30
```

`--after` / `--before` を指定した場合、`--days` オプションは無視されます。

### リアルタイム監視

Pub/Sub でメール受信を検知し、自動的に PDF 化します。

```bash
uv run python -m gmail_automation watch
```

`Ctrl+C` で停止します。

### メールのパース

取得した Daily Confirmation メールの HTML をパースし、Deals・Positions・A/C Summary を構造化データ（JSONL）として出力します。

```bash
# デフォルト（output/emails.jsonl → output/parsed_confirmations.jsonl）
uv run python -m gmail_automation parse

# 入出力ファイルを指定
uv run python -m gmail_automation parse --input output/emails.jsonl --output output/parsed_confirmations.jsonl
```

### 日別損益算出

パース済みの Daily Confirmation データから、アカウント別・日別の USD 損益を算出します。

```bash
# デフォルト（output/parsed_confirmations.jsonl → output/daily_pnl.jsonl）
uv run python -m gmail_automation daily-pnl --input-path output/parsed_confirmations.jsonl --output-path output/daily_pnl.jsonl
```

### コマンド一覧

| コマンド | 説明 |
|---|---|
| `auth` | OAuth2 認証を実行 |
| `fetch` | 手動でメールを取得して PDF 化 |
| `parse` | Daily Confirmation メールをパースして JSONL 出力 |
| `daily-pnl` | 日別 USD 損益を算出して JSONL 出力 |
| `watch` | Pub/Sub でリアルタイム監視 |
| `config-init` | 設定ファイルのテンプレートを生成 |

各コマンドに `--config` / `-c` オプションで設定ファイルパスを指定できます（デフォルト: `config.yaml`）。

## 出力

PDF は `config.yaml` の `output.directory`（デフォルト: `./output/`）に保存されます。
ファイル名は `output.filename_template` で制御できます。

```
output/
  2026-03-05_sender@example.com_件名.pdf
  2026-03-04_sender@example.com_別の件名.pdf
```

## テスト

```bash
uv run pytest tests/ -v
```

## プロジェクト構成

```
gmail_automation/
├── pyproject.toml
├── config.yaml.example
├── docs/
│   ├── coding_style.md
│   └── setup.md              # GCP セットアップ詳細手順
├── src/gmail_automation/
│   ├── __main__.py            # CLI エントリポイント
│   ├── cli.py                 # typer CLI コマンド定義
│   ├── config.py              # 設定管理（pydantic）
│   ├── auth.py                # OAuth2 認証
│   ├── gmail_client.py        # Gmail API クライアント
│   ├── converter.py           # HTML/テキスト → PDF 変換
│   ├── parser.py              # Daily Confirmation HTML パーサー
│   ├── daily_pnl.py           # 日別 USD 損益算出
│   ├── processor.py           # メール処理パイプライン
│   └── pubsub_listener.py     # Pub/Sub リアルタイム監視
├── credentials/               # 認証情報（git 管理外）
├── output/                    # PDF 出力先（git 管理外）
└── tests/
```
