"""Gmail API OAuth2認証モジュール。

OAuth2認証フローを管理し、トークンの取得・リフレッシュ・保存を行う。
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API で使用するスコープ
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/pubsub",
]


def authenticate(credentials_file: Path, token_file: Path) -> Credentials:
    """OAuth2認証を行い、有効な認証情報を返す。

    既存トークンがあればロードし、期限切れならリフレッシュする。
    トークンが存在しない場合はOAuth2フローで新規認証を行う。
    認証完了後、トークンをファイルに保存する。

    Args:
        credentials_file: OAuth2クライアント認証情報のJSONファイルパス。
        token_file: トークン保存先のファイルパス。

    Returns:
        有効なOAuth2認証情報。
    """
    creds: Credentials | None = None

    # 既存トークンファイルがあればロード
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    # トークンが無効または期限切れの場合の処理
    if creds is None or not creds.valid:
        if creds is not None and creds.expired and creds.refresh_token:
            # 期限切れトークンをリフレッシュ
            creds.refresh(Request())
        else:
            # 新規OAuth2認証フローを実行
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # トークンをファイルに保存
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json())

    return creds
