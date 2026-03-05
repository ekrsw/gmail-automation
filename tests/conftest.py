"""テスト共通フィクスチャ"""

import base64
import sys
from unittest.mock import MagicMock

# WeasyPrintはシステムライブラリ（libgobject等）に依存するため、
# テスト環境ではモックに差し替える
_mock_weasyprint = MagicMock()
sys.modules.setdefault("weasyprint", _mock_weasyprint)

import pytest

from gmail_automation.config import AppConfig


@pytest.fixture()
def sample_config(tmp_path):
    """テスト用AppConfigインスタンスを返す。出力先にtmpディレクトリを使用する。"""
    return AppConfig(
        gmail={
            "target_senders": ["target@example.com"],
            "unread_only": False,
        },
        pubsub={
            "project_id": "test-project",
            "topic_name": "test-topic",
            "subscription_name": "test-sub",
        },
        output={
            "directory": str(tmp_path / "output"),
            "filename_template": "{date}_{sender}_{subject}",
        },
        auth={
            "credentials_file": str(tmp_path / "credentials" / "credentials.json"),
            "token_file": str(tmp_path / "credentials" / "token.json"),
        },
        logging={
            "level": "DEBUG",
        },
    )


def _encode_base64url(text: str) -> str:
    """テスト用: 文字列をbase64urlエンコードする。"""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


@pytest.fixture()
def sample_message():
    """Gmail APIメッセージのサンプル辞書を返す。payload, headers, body含む。"""
    html_body = "<p>テストメール本文</p>"
    text_body = "テストメール本文"

    return {
        "id": "msg_001",
        "threadId": "thread_001",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "target@example.com"},
                {"name": "Subject", "value": "テスト件名"},
                {"name": "Date", "value": "2026-03-01"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": _encode_base64url(text_body),
                    },
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": _encode_base64url(html_body),
                    },
                },
            ],
        },
    }
