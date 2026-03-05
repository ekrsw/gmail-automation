"""converter モジュールのテスト"""

import json
from pathlib import Path

import pytest

from gmail_automation.converter import (
    generate_filename,
    build_mail_record,
    append_to_jsonl,
)


class TestGenerateFilename:
    """generate_filename関数のテスト"""

    def test_generate_filename(self):
        """テンプレートに基づいてファイル名が正しく生成される。"""
        result = generate_filename(
            date_str="2026-03-01",
            sender="user@example.com",
            subject="テスト件名",
            template="{date}_{sender}_{subject}",
        )

        assert "2026-03-01" in result
        assert "user@example.com" in result
        assert "テスト件名" in result

    def test_generate_filename_special_chars(self):
        """ファイル名に使用できない特殊文字が除去される。"""
        result = generate_filename(
            date_str="2026-03-01",
            sender="user",
            subject='件名:テスト/"引用"',
            template="{date}_{sender}_{subject}",
        )

        # コロン、スラッシュ、ダブルクォートが除去される
        assert ":" not in result
        assert "/" not in result
        assert '"' not in result

    def test_generate_filename_max_length(self):
        """ファイル名が最大長（100文字）を超えないことを確認する。"""
        long_subject = "あ" * 200

        result = generate_filename(
            date_str="2026-03-01",
            sender="user",
            subject=long_subject,
            template="{date}_{sender}_{subject}",
        )

        assert len(result) <= 100


class TestBuildMailRecord:
    """build_mail_record関数のテスト"""

    def test_build_mail_record(self):
        """メッセージからJSONLレコードが正しく構築される。"""
        message = {
            "id": "msg_001",
            "threadId": "thread_001",
            "labelIds": ["INBOX", "UNREAD"],
        }

        record = build_mail_record(
            message=message,
            sender="test@example.com",
            subject="テスト件名",
            date_str="2026-03-01",
            html_body="<p>本文</p>",
            text_body="本文",
        )

        assert record["message_id"] == "msg_001"
        assert record["thread_id"] == "thread_001"
        assert record["sender"] == "test@example.com"
        assert record["subject"] == "テスト件名"
        assert record["date"] == "2026-03-01"
        assert record["html_body"] == "<p>本文</p>"
        assert record["text_body"] == "本文"
        assert record["labels"] == ["INBOX", "UNREAD"]
        assert "fetched_at" in record

    def test_build_mail_record_none_body(self):
        """本文がNoneの場合に空文字列が設定される。"""
        message = {"id": "msg_002", "threadId": "thread_002"}

        record = build_mail_record(
            message=message,
            sender="test@example.com",
            subject="テスト",
            date_str="2026-03-01",
            html_body=None,
            text_body=None,
        )

        assert record["html_body"] == ""
        assert record["text_body"] == ""
        assert record["labels"] == []


class TestAppendToJsonl:
    """append_to_jsonl関数のテスト"""

    def test_append_to_jsonl(self, tmp_path):
        """レコードがJSONLファイルに正しく追記される。"""
        output_path = tmp_path / "output" / "emails.jsonl"
        record = {"message_id": "msg_001", "subject": "テスト"}

        result = append_to_jsonl(record, output_path)

        assert result == output_path
        assert output_path.exists()

        line = output_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        assert parsed["message_id"] == "msg_001"
        assert parsed["subject"] == "テスト"

    def test_append_to_jsonl_multiple(self, tmp_path):
        """複数レコードが1行1レコードで追記される。"""
        output_path = tmp_path / "emails.jsonl"

        append_to_jsonl({"message_id": "msg_001"}, output_path)
        append_to_jsonl({"message_id": "msg_002"}, output_path)

        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["message_id"] == "msg_001"
        assert json.loads(lines[1])["message_id"] == "msg_002"
