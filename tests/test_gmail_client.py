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


class TestFetchMessages:
    """fetch_messagesメソッドのテスト"""

    def test_fetch_messages_pagination(self, gmail_client):
        """nextPageTokenが存在する場合に2ページ分取得される。"""
        service = gmail_client._service
        list_mock = service.users.return_value.messages.return_value.list

        page1_response = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}],
            "nextPageToken": "token_page2",
        }
        page2_response = {
            "messages": [{"id": "msg3"}],
        }
        list_mock.return_value.execute.side_effect = [
            page1_response,
            page2_response,
        ]

        service.users.return_value.messages.return_value.get.return_value.execute.side_effect = [
            {"id": "msg1", "payload": {}},
            {"id": "msg2", "payload": {}},
            {"id": "msg3", "payload": {}},
        ]

        results = gmail_client.fetch_messages(query="test")

        assert len(results) == 3
        assert list_mock.call_count == 2

        first_call_kwargs = list_mock.call_args_list[0][1]
        assert "pageToken" not in first_call_kwargs

        second_call_kwargs = list_mock.call_args_list[1][1]
        assert second_call_kwargs["pageToken"] == "token_page2"

    def test_fetch_messages_single_page(self, gmail_client):
        """nextPageTokenがない場合に1回で終了する。"""
        service = gmail_client._service
        list_mock = service.users.return_value.messages.return_value.list

        list_mock.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}],
        }

        service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "msg1",
            "payload": {},
        }

        results = gmail_client.fetch_messages()

        assert len(results) == 1
        assert list_mock.call_count == 1


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
