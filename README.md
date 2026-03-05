# Gmail メール自動取得・分析システム

特定の差出人からの Gmail メールを自動取得し、構造化データ（JSONL）として保存・分析するシステムです。
Daily Confirmation メールのパースやアカウント別日別損益の算出に対応しています。

## 機能

- 指定した差出人からのメールを自動取得（手動フェッチ / Pub/Sub リアルタイム監視）
- メール本文を JSONL 形式で保存
- Daily Confirmation メールの HTML パース（Deals・Positions・A/C Summary を構造化）
- アカウント別・日別 USD 損益の5要素分解
- 処理済みメールの重複排除

## データパイプライン

```
fetch (Gmail API) → emails.jsonl
                       ↓
                    parse → parsed_confirmations.jsonl
                               ↓
                            daily-pnl → daily_pnl.jsonl
```

## 前提条件

- Python 3.11 以上
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- Google Cloud Platform アカウント

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

### メール取得（fetch）

過去 N 日分のメールを取得して JSONL に保存します。

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

### リアルタイム監視（watch）

Pub/Sub でメール受信を検知し、自動的に JSONL へ保存します。

```bash
uv run python -m gmail_automation watch
```

`Ctrl+C` で停止します。

### メールのパース（parse）

取得した Daily Confirmation メールの HTML をパースし、Deals・Positions・A/C Summary を構造化データ（JSONL）として出力します。

```bash
# デフォルト（output/emails.jsonl → output/parsed_confirmations.jsonl）
uv run python -m gmail_automation parse

# 入出力ファイルを指定
uv run python -m gmail_automation parse --input output/emails.jsonl --output output/parsed_confirmations.jsonl
```

### 日別損益算出（daily-pnl）

パース済みの Daily Confirmation データから、アカウント別・日別の USD 損益を5要素に分解して算出します。JPY 通貨のアカウントは除外されます。

```bash
# デフォルト（output/parsed_confirmations.jsonl → output/daily_pnl.jsonl）
uv run python -m gmail_automation daily-pnl

# 入出力ファイルを指定
uv run python -m gmail_automation daily-pnl --input-path output/parsed_confirmations.jsonl --output-path output/daily_pnl.jsonl
```

#### 5要素の定義

| 要素 | データソース | 説明 |
|------|-------------|------|
| `deposit_withdrawal` | `account_summary.deposit_withdrawal` | 入出金 |
| `commission` | `sum(deals[].commission + deals[].fee)` | 手数料 |
| `swap` | `sum(deals[].swap)` | スワップ |
| `profit` | `sum(deals[].profit)` | 純トレーディング損益 |
| `balance` | `account_summary.balance` | 残高 |

※ `commission + swap + profit` = 日次変動額（入出金除く）

#### 出力例

```json
{
  "date": "2025.12.22",
  "accounts": {
    "7379730": {
      "deposit_withdrawal": 0.0,
      "commission": -16.1,
      "swap": 0.0,
      "profit": 491.28,
      "balance": 35772.4
    }
  },
  "total": {
    "deposit_withdrawal": 0.0,
    "commission": -54.56,
    "swap": -3.84,
    "profit": 2376.72,
    "balance": 88106.08
  }
}
```

### コマンド一覧

| コマンド | 説明 |
|---|---|
| `auth` | OAuth2 認証を実行 |
| `fetch` | メールを取得して JSONL に保存 |
| `parse` | Daily Confirmation メールをパースして JSONL 出力 |
| `daily-pnl` | アカウント別・日別 USD 損益を5要素分解して JSONL 出力 |
| `watch` | Pub/Sub でリアルタイム監視・JSONL 保存 |
| `config-init` | 設定ファイルのテンプレートを生成 |

各コマンドに `--config` / `-c` オプションで設定ファイルパスを指定できます（デフォルト: `config.yaml`）。

## 出力

すべての出力は `output/` ディレクトリに保存されます（`config.yaml` で変更可能）。

| ファイル | 生成コマンド | 内容 |
|---------|-------------|------|
| `emails.jsonl` | `fetch` / `watch` | 取得したメールの生データ（HTML本文含む） |
| `parsed_confirmations.jsonl` | `parse` | パース済み構造化データ（Deals・Positions・A/C Summary） |
| `daily_pnl.jsonl` | `daily-pnl` | アカウント別・日別 USD 損益（5要素分解） |

## テスト

```bash
uv run pytest tests/ -v
```

## プロジェクト構成

```
gmail-automation/
├── pyproject.toml
├── config.yaml.example
├── docs/
│   ├── coding_style.md
│   └── setup.md              # GCP セットアップ詳細手順
├── src/gmail_automation/
│   ├── __init__.py
│   ├── __main__.py            # CLI エントリポイント
│   ├── cli.py                 # typer CLI コマンド定義
│   ├── config.py              # 設定管理（pydantic）
│   ├── auth.py                # OAuth2 認証
│   ├── gmail_client.py        # Gmail API クライアント
│   ├── converter.py           # メールデータ → JSONL レコード変換
│   ├── parser.py              # Daily Confirmation HTML パーサー
│   ├── daily_pnl.py           # アカウント別・日別 USD 損益算出（5要素分解）
│   ├── processor.py           # メール取得・保存パイプライン
│   └── pubsub_listener.py     # Pub/Sub リアルタイム監視
├── credentials/               # 認証情報（git 管理外）
├── output/                    # データ出力先（git 管理外）
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_converter.py
    ├── test_gmail_client.py
    ├── test_parser.py
    └── test_processor.py
```
