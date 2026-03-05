"""設定管理モジュール

pydantic + PyYAML による config.yaml のバリデーションと読み込みを行う。
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

# デフォルト設定ファイルパス（プロジェクトルート）
DEFAULT_CONFIG_PATH = Path("config.yaml")


class GmailConfig(BaseModel):
    """Gmail関連の設定"""

    target_senders: list[str] = Field(
        default_factory=list,
        description="監視対象の送信者メールアドレス一覧",
    )
    unread_only: bool = Field(
        default=False,
        description="未読メールのみを対象とするかどうか",
    )


class PubSubConfig(BaseModel):
    """Google Cloud Pub/Sub関連の設定"""

    project_id: str = Field(description="GCPプロジェクトID")
    topic_name: str = Field(
        default="gmail-notifications",
        description="Pub/Subトピック名",
    )
    subscription_name: str = Field(
        default="gmail-notifications-sub",
        description="Pub/Subサブスクリプション名",
    )


class OutputConfig(BaseModel):
    """出力関連の設定"""

    directory: Path = Field(
        default=Path("./output"),
        description="JSONL出力先ディレクトリ",
    )
    filename_template: str = Field(
        default="{date}_{sender}_{subject}",
        description="出力ファイル名のテンプレート",
    )


class AuthConfig(BaseModel):
    """認証関連の設定"""

    credentials_file: Path = Field(
        default=Path("./credentials/credentials.json"),
        description="OAuth2クレデンシャルファイルのパス",
    )
    token_file: Path = Field(
        default=Path("./credentials/token.json"),
        description="認証トークンファイルのパス",
    )


class LoggingConfig(BaseModel):
    """ロギング関連の設定"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="ログレベル",
    )
    file: Path | None = Field(
        default=None,
        description="ログファイルのパス（Noneの場合は標準出力のみ）",
    )


class AppConfig(BaseModel):
    """アプリケーション全体の設定"""

    gmail: GmailConfig = Field(default_factory=GmailConfig)
    pubsub: PubSubConfig
    output: OutputConfig = Field(default_factory=OutputConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """設定ファイルを読み込み、バリデーション済みの設定オブジェクトを返す。

    Args:
        path: 設定ファイルのパス。デフォルトはプロジェクトルートの config.yaml。

    Returns:
        バリデーション済みの AppConfig インスタンス。

    Raises:
        FileNotFoundError: 設定ファイルが存在しない場合。
        yaml.YAMLError: YAMLの構文エラーが発生した場合。
        pydantic.ValidationError: 設定値のバリデーションに失敗した場合。
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with config_path.open(encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if raw_config is None:
        raise ValueError(f"設定ファイルが空です: {config_path}")

    return AppConfig.model_validate(raw_config)


def generate_config_template() -> str:
    """設定ファイルのテンプレートをYAML文字列として生成する。

    Returns:
        config.yaml のテンプレート文字列。
    """
    template = {
        "gmail": {
            "target_senders": ["sender@example.com"],
            "unread_only": False,
        },
        "pubsub": {
            "project_id": "your-gcp-project-id",
            "topic_name": "gmail-notifications",
            "subscription_name": "gmail-notifications-sub",
        },
        "output": {
            "directory": "./output",
            "filename_template": "{date}_{sender}_{subject}",
        },
        "auth": {
            "credentials_file": "./credentials/credentials.json",
            "token_file": "./credentials/token.json",
        },
        "logging": {
            "level": "INFO",
            "file": None,
        },
    }
    return yaml.dump(template, default_flow_style=False, allow_unicode=True, sort_keys=False)
