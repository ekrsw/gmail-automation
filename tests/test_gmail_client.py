"""gmail_client モジュールのテスト"""

import base64
from unittest.mock import MagicMock

import pytest

from gmail_automation.gmail_client import GmailClient


def _encode(text: str) -> str:
    """テスト用base64urlエンコード"""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


@pytest.fixture()
def gmail_client(mocker):
    """GmailClientインスタンスを返す。discovery.buildをモックする。"""
    mocker.patch("gmail_automation.gmail_client.build", return_value=MagicMock())
    creds = MagicMock()
    return GmailClient(credentials=creds)


class TestExtractBody:
    """extract_bodyメソッドのテスト"""

    def test_extract_body_html_and_text(self, gmail_client, sample_message):
        """HTML・テキスト両方を含むメッセージから正しく抽出できる。"""
        html_body, text_body = gmail_client.extract_body(sample_message)

        assert "テストメール本文" in html_body
        assert "<p>" in html_body
        assert "テストメール本文" in text_body

    def test_extract_body_text_only(self, gmail_client):
        """テキストのみのメッセージからプレーンテキストを抽出できる。"""
        message = {
            "payload": {
                "mimeType": "text/plain",
                "body": {
                    "data": _encode("プレーンテキストのみ"),
                },
                "headers": [],
            },
        }

        html_body, text_body = gmail_client.extract_body(message)

        assert html_body == ""
        assert "プレーンテキストのみ" in text_body


class TestExtractHeaders:
    """ヘッダー抽出メソッドのテスト"""

    def test_extract_sender(self, gmail_client, sample_message):
        """Fromヘッダーからメールアドレスを抽出できる。"""
        sender = gmail_client.extract_sender(sample_message)

        assert sender == "target@example.com"

    def test_extract_subject(self, gmail_client, sample_message):
        """Subjectヘッダーを抽出できる。"""
        subject = gmail_client.extract_subject(sample_message)

        assert subject == "テスト件名"
