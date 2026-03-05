# GCP セットアップ手順

Gmail Automation プロジェクトの環境構築および GCP 設定手順を説明します。

## 前提条件

以下のツールおよびアカウントが必要です。

- Python 3.11 以上
- uv パッケージマネージャー
- Google Cloud Platform アカウント
- macOS の場合: WeasyPrint のシステム依存パッケージ

```bash
# macOS: WeasyPrint の依存パッケージをインストール
brew install pango gdk-pixbuf libffi
```

## 1. プロジェクトセットアップ

仮想環境を作成し、依存パッケージをインストールします。

```bash
# 仮想環境の構築
uv venv

# 仮想環境の有効化
source .venv/bin/activate

# 開発用依存を含めてインストール
uv pip install -e ".[dev]"
```

## 2. GCP プロジェクト設定

### 2.1 プロジェクト作成

1. [GCP コンソール](https://console.cloud.google.com/) にアクセスする
2. 画面上部のプロジェクトセレクタから「新しいプロジェクト」を選択する
3. プロジェクト名を入力し、「作成」をクリックする

### 2.2 API の有効化

1. 作成したプロジェクトを選択する
2. 「API とサービス」>「ライブラリ」に移動する
3. 以下の API を検索し、それぞれ有効化する
   - **Gmail API**
   - **Cloud Pub/Sub API**

### 2.3 OAuth2 クレデンシャル作成

1. 「API とサービス」>「認証情報」に移動する
2. 「認証情報を作成」>「OAuth クライアント ID」を選択する
3. アプリケーションの種類で「デスクトップアプリケーション」を選択する
4. 名前を入力し、「作成」をクリックする
5. JSON ファイルをダウンロードし、`credentials.json` にリネームする
6. プロジェクトの `credentials/` ディレクトリに配置する

```bash
# credentials ディレクトリがない場合は作成
mkdir -p credentials

# ダウンロードしたファイルを配置
mv ~/Downloads/client_secret_*.json credentials/credentials.json
```

## 3. Pub/Sub 設定

Gmail のリアルタイム通知を受信するために Pub/Sub を設定します。

### 3.1 トピック作成

1. 「Pub/Sub」>「トピック」に移動する
2. 「トピックを作成」をクリックする
3. トピック ID に `gmail-notifications` を入力する
4. 「作成」をクリックする

### 3.2 権限の付与

Gmail API がトピックにメッセージを Publish できるよう権限を設定します。

1. 作成したトピック `gmail-notifications` を選択する
2. 「権限」タブを開く
3. 「プリンシパルを追加」をクリックする
4. 以下の情報を入力する
   - **新しいプリンシパル**: `gmail-api-push@system.gserviceaccount.com`
   - **ロール**: 「Pub/Sub パブリッシャー」
5. 「保存」をクリックする

### 3.3 サブスクリプション作成

1. 「Pub/Sub」>「サブスクリプション」に移動する
2. 「サブスクリプションを作成」をクリックする
3. 以下の情報を入力する
   - **サブスクリプション ID**: `gmail-notifications-sub`
   - **トピック**: `gmail-notifications`
   - **配信タイプ**: Pull
4. 「作成」をクリックする

## 4. 設定ファイル準備

設定ファイルのテンプレートを生成し、実際の値を設定します。

```bash
# 設定ファイルのテンプレートを生成
uv run python -m gmail_automation config-init
```

生成された `config.yaml` を開き、以下の項目を環境に合わせて編集してください。

- GCP プロジェクト ID
- Pub/Sub トピック名
- Pub/Sub サブスクリプション名
- その他プロジェクト固有の設定

## 5. 初回認証

OAuth2 認証フローを実行し、アクセストークンを取得します。

```bash
uv run python -m gmail_automation auth
```

ブラウザが自動的に開き、Google アカウントでのログインと権限の許可を求められます。許可すると、トークンが自動的に保存されます。

## 6. 動作確認

### 手動フェッチ

直近 7 日間のメールを取得して動作を確認します。

```bash
uv run python -m gmail_automation fetch --days 7
```

### リアルタイム監視

Pub/Sub 経由のリアルタイム通知による監視を開始します。

```bash
uv run python -m gmail_automation watch
```

新着メールが届くと、自動的に処理が実行されます。`Ctrl+C` で停止できます。

## トラブルシューティング

### 認証エラー

**症状**: `invalid_grant` や `token has been expired or revoked` と表示される

**対処法**:

1. 保存済みのトークンファイルを削除する

   ```bash
   rm credentials/token.json
   ```

2. 再度認証を実行する

   ```bash
   uv run python -m gmail_automation auth
   ```

3. それでも解決しない場合は、GCP コンソールで OAuth クライアントを再作成する

### Pub/Sub 通知が届かない

**症状**: `watch` コマンドを実行しても新着メールの通知が受信されない

**対処法**:

1. トピックの権限設定を確認する
   - `gmail-api-push@system.gserviceaccount.com` に Pub/Sub パブリッシャーロールが付与されているか確認する
2. サブスクリプションが正しいトピックに紐づいているか確認する
3. Gmail API の `watch` リクエストが正常に完了しているかログを確認する
4. `watch` の有効期限（7 日間）が切れていないか確認する。期限切れの場合は再度 `watch` を実行する

### WeasyPrint のフォント問題

**症状**: PDF 出力時に文字化けや豆腐（四角）が表示される

**対処法**:

1. システム依存パッケージがインストールされているか確認する

   ```bash
   brew install pango gdk-pixbuf libffi
   ```

2. 日本語フォントがインストールされているか確認する

   ```bash
   # 利用可能なフォントを確認
   fc-list :lang=ja
   ```

3. 日本語フォントがない場合はインストールする

   ```bash
   # Noto フォントの例
   brew install font-noto-sans-cjk-jp
   ```

4. フォントキャッシュを更新する

   ```bash
   fc-cache -fv
   ```
