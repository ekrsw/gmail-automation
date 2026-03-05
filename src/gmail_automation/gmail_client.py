"""Gmail APIクライアントモジュール。

Gmail APIとの通信を担当し、メッセージの取得・解析・Pub/Sub通知管理を行う。
"""

import base64

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource


class GmailClient:
    """Gmail APIクライアント。

    Gmail APIサービスを通じてメッセージの取得、解析、
    履歴の追跡、Pub/Sub通知の管理を行う。
    """

    def __init__(self, credentials: Credentials) -> None:
        """Gmail APIサービスオブジェクトを構築する。

        Args:
            credentials: OAuth2認証情報。
        """
        self._service: Resource = build("gmail", "v1", credentials=credentials)

    def fetch_messages(self, query: str = "") -> list[dict]:
        """メッセージ一覧を取得し、各メッセージの詳細を返す。

        nextPageTokenを使って全ページを取得する。

        Args:
            query: Gmail検索クエリ文字列。

        Returns:
            メッセージ詳細のリスト。
        """
        all_messages: list[dict] = []
        page_token: str | None = None

        while True:
            params: dict = {"userId": "me", "q": query, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token

            response = (
                self._service.users()
                .messages()
                .list(**params)
                .execute()
            )

            messages = response.get("messages", [])
            all_messages.extend(messages)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return [
            self.get_message_detail(msg["id"]) for msg in all_messages
        ]

    def get_message_detail(self, message_id: str) -> dict:
        """単一メッセージの詳細を取得する。

        Args:
            message_id: メッセージID。

        Returns:
            メッセージの詳細データ。
        """
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def extract_body(self, message: dict) -> tuple[str, str]:
        """メッセージからHTML本文とプレーンテキスト本文を抽出する。

        MIME構造を再帰的にパースし、text/htmlとtext/plainパートを取得する。

        Args:
            message: メッセージの詳細データ。

        Returns:
            (html_body, text_body) のタプル。該当パートがない場合は空文字列。
        """
        html_body = ""
        text_body = ""

        payload = message.get("payload", {})
        html_body, text_body = self._parse_parts(payload)

        return html_body, text_body

    def _parse_parts(self, part: dict) -> tuple[str, str]:
        """MIMEパートを再帰的に探索してHTML本文とプレーンテキスト本文を取得する。

        Args:
            part: MIMEパートデータ。

        Returns:
            (html_body, text_body) のタプル。
        """
        html_body = ""
        text_body = ""

        mime_type = part.get("mimeType", "")

        # パートにbodyのdataが直接含まれている場合
        body = part.get("body", {})
        data = body.get("data", "")

        if data:
            decoded = self._decode_base64url(data)
            if mime_type == "text/html":
                html_body = decoded
            elif mime_type == "text/plain":
                text_body = decoded

        # 子パートがある場合は再帰的に探索
        parts = part.get("parts", [])
        for sub_part in parts:
            sub_html, sub_text = self._parse_parts(sub_part)
            if sub_html and not html_body:
                html_body = sub_html
            if sub_text and not text_body:
                text_body = sub_text

        return html_body, text_body

    @staticmethod
    def _decode_base64url(data: str) -> str:
        """base64urlエンコードされたデータをデコードする。

        Args:
            data: base64urlエンコードされた文字列。

        Returns:
            デコードされた文字列。
        """
        return base64.urlsafe_b64decode(data + "==").decode("utf-8")

    def extract_sender(self, message: dict) -> str:
        """Fromヘッダーからメールアドレスを抽出する。

        Args:
            message: メッセージの詳細データ。

        Returns:
            送信者のメールアドレス。見つからない場合は空文字列。
        """
        return self._get_header(message, "From")

    def extract_subject(self, message: dict) -> str:
        """Subjectヘッダーを抽出する。

        Args:
            message: メッセージの詳細データ。

        Returns:
            メールの件名。見つからない場合は空文字列。
        """
        return self._get_header(message, "Subject")

    def extract_date(self, message: dict) -> str:
        """Dateヘッダーを抽出する。

        Args:
            message: メッセージの詳細データ。

        Returns:
            メールの日付文字列。見つからない場合は空文字列。
        """
        return self._get_header(message, "Date")

    @staticmethod
    def _get_header(message: dict, header_name: str) -> str:
        """メッセージのpayload.headersから指定ヘッダーの値を取得する。

        Args:
            message: メッセージの詳細データ。
            header_name: 取得するヘッダー名。

        Returns:
            ヘッダーの値。見つからない場合は空文字列。
        """
        headers = message.get("payload", {}).get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == header_name.lower():
                return header.get("value", "")
        return ""

    def get_history(self, start_history_id: str) -> list[dict]:
        """指定されたhistoryId以降の変更履歴を取得する。

        messagesAddedイベントからメッセージIDリストを返す。

        Args:
            start_history_id: 取得開始のhistoryId。

        Returns:
            追加されたメッセージのリスト。各要素はmessageの辞書。
        """
        response = (
            self._service.users()
            .history()
            .list(userId="me", startHistoryId=start_history_id)
            .execute()
        )

        messages_added: list[dict] = []
        history_records = response.get("history", [])
        for record in history_records:
            for added in record.get("messagesAdded", []):
                messages_added.append(added.get("message", {}))

        return messages_added

    def watch(self, topic_name: str) -> dict:
        """Pub/Sub通知を登録する。

        指定されたCloud Pub/Subトピックに対してGmail通知を設定する。

        Args:
            topic_name: Cloud Pub/Subのトピック名
                （例: projects/my-project/topics/gmail-notifications）。

        Returns:
            watchレスポンス。historyIdとexpirationを含む。
        """
        request_body = {
            "topicName": topic_name,
            "labelIds": ["INBOX"],
        }
        return (
            self._service.users()
            .watch(userId="me", body=request_body)
            .execute()
        )

    def fetch_messages_by_sender(self, sender: str) -> list[dict]:
        """指定した送信者からのメッセージを取得する。

        Args:
            sender: 送信者のメールアドレス。

        Returns:
            メッセージ詳細のリスト。
        """
        query = f"from:{sender}"
        return self.fetch_messages(query=query)
