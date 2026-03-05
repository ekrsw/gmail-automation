"""CLIコマンド定義モジュール。

typerによるCLIインターフェースを提供する。
"""

import logging
from pathlib import Path

import typer

from gmail_automation.config import (
    DEFAULT_CONFIG_PATH,
    generate_config_template,
    load_config,
)

app = typer.Typer(help="Gmail メール自動PDF化ツール")


def _setup_logging(level: str, log_file: Path | None = None) -> None:
    """ロギングを設定する。

    Args:
        level: ログレベル文字列。
        log_file: ログファイルパス。Noneの場合は標準出力のみ。
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


@app.command()
def auth(
    config_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH, "--config", "-c", help="設定ファイルのパス",
    ),
) -> None:
    """OAuth2認証を実行する。"""
    config = load_config(config_path)
    _setup_logging(config.logging.level, config.logging.file)

    from gmail_automation.auth import authenticate

    creds = authenticate(config.auth.credentials_file, config.auth.token_file)
    typer.echo(f"認証完了: トークン保存先={config.auth.token_file}")
    if creds.valid:
        typer.echo("トークンは有効です")


@app.command()
def fetch(
    days: int = typer.Option(7, "--days", "-d", help="取得対象の日数（--after/--before未指定時に使用）"),
    after: str | None = typer.Option(None, "--after", "-a", help="取得開始日（YYYY/MM/DD形式）"),
    before: str | None = typer.Option(None, "--before", "-b", help="取得終了日（YYYY/MM/DD形式）"),
    force: bool = typer.Option(False, "--force", "-f", help="処理済みIDをクリアして再取得する"),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH, "--config", "-c", help="設定ファイルのパス",
    ),
) -> None:
    """メールを取得してPDF化する。

    --after/--beforeで日付範囲を指定するか、--daysで過去N日分を取得する。
    """
    config = load_config(config_path)
    _setup_logging(config.logging.level, config.logging.file)

    from gmail_automation.auth import authenticate
    from gmail_automation.gmail_client import GmailClient
    from gmail_automation.processor import MailProcessor

    creds = authenticate(config.auth.credentials_file, config.auth.token_file)
    gmail_client = GmailClient(creds)
    processor = MailProcessor(config, gmail_client)

    if force:
        processor.clear_processed_ids()
        typer.echo("処理済みIDをクリアしました")

    pdfs = processor.fetch_and_process(days=days, after=after, before=before)
    typer.echo(f"処理完了: {len(pdfs)}件のPDFを生成しました")
    for pdf_path in pdfs:
        typer.echo(f"  - {pdf_path}")


@app.command()
def watch(
    config_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH, "--config", "-c", help="設定ファイルのパス",
    ),
) -> None:
    """Pub/Subでリアルタイム監視を開始する。"""
    config = load_config(config_path)
    _setup_logging(config.logging.level, config.logging.file)

    from gmail_automation.auth import authenticate
    from gmail_automation.gmail_client import GmailClient
    from gmail_automation.processor import MailProcessor
    from gmail_automation.pubsub_listener import PubSubListener

    creds = authenticate(config.auth.credentials_file, config.auth.token_file)
    gmail_client = GmailClient(creds)
    processor = MailProcessor(config, gmail_client)
    listener = PubSubListener(config, gmail_client, processor)

    typer.echo("リアルタイム監視を開始します（Ctrl+Cで停止）")
    listener.start()


@app.command()
def config_init(
    output_path: Path = typer.Option(
        DEFAULT_CONFIG_PATH, "--output", "-o", help="出力先パス",
    ),
) -> None:
    """設定ファイルのテンプレートを生成する。"""
    if output_path.exists():
        overwrite = typer.confirm(f"{output_path} は既に存在します。上書きしますか？")
        if not overwrite:
            typer.echo("キャンセルしました")
            raise typer.Exit()

    template = generate_config_template()
    output_path.write_text(template, encoding="utf-8")
    typer.echo(f"設定テンプレートを生成しました: {output_path}")
