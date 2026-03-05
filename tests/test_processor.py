"""processor モジュールのテスト"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gmail_automation.processor import ProcessedIdStore, MailProcessor


class TestProcessedIdStore:
    """ProcessedIdStoreのテスト"""

    def test_load_empty(self, tmp_path):
        """ファイルが存在しない場合に空セットを返す。"""
        store = ProcessedIdStore(store_path=tmp_path / "ids.json")

        assert store.load() == set()

    def test_save_and_load(self, tmp_path):
        """保存したIDを正しく読み込めることを確認する。"""
        store_path = tmp_path / "ids.json"
        store = ProcessedIdStore(store_path=store_path)

        store.save({"msg_001", "msg_002"})
        loaded = store.load()

        assert loaded == {"msg_001", "msg_002"}

    def test_is_processed(self, tmp_path):
        """処理済みIDの判定が正しく動作することを確認する。"""
        store_path = tmp_path / "ids.json"
        store = ProcessedIdStore(store_path=store_path)
        store.save({"msg_001"})

        assert store.is_processed("msg_001") is True
        assert store.is_processed("msg_999") is False

    def test_mark_processed(self, tmp_path):
        """mark_processedでIDが追加されることを確認する。"""
        store_path = tmp_path / "ids.json"
        store = ProcessedIdStore(store_path=store_path)

        store.mark_processed("msg_001")
        store.mark_processed("msg_002")

        assert store.is_processed("msg_001") is True
        assert store.is_processed("msg_002") is True


class TestMailProcessor:
    """MailProcessorのテスト"""

    @pytest.fixture()
    def mock_gmail_client(self):
        """モック化されたGmailClientを返す。"""
        client = MagicMock()
        client.extract_sender.return_value = "target@example.com"
        client.extract_subject.return_value = "テスト件名"
        client.extract_date.return_value = "2026-03-01"
        client.extract_body.return_value = ("<p>本文</p>", "本文")
        return client

    @pytest.fixture()
    def processor(self, sample_config, mock_gmail_client):
        """テスト用MailProcessorインスタンスを返す。"""
        return MailProcessor(config=sample_config, gmail_client=mock_gmail_client)

    def test_process_messages_filters_sender(
        self, processor, mock_gmail_client
    ):
        """対象外の差出人のメッセージがスキップされることを確認する。"""
        mock_gmail_client.extract_sender.return_value = "unknown@example.com"

        messages = [{"id": "msg_001"}]
        result = processor.process_messages(messages)

        assert result == []

    def test_process_messages_skips_processed(
        self, processor, mock_gmail_client
    ):
        """処理済みメッセージがスキップされることを確認する。"""
        # 事前にmsg_001を処理済みとしてマーク
        processor._id_store.mark_processed("msg_001")

        messages = [{"id": "msg_001"}]
        result = processor.process_messages(messages)

        assert result == []
        # extract_senderは呼ばれないはず（重複チェックが先に実行される）
        mock_gmail_client.extract_sender.assert_not_called()

    def test_process_messages_saves_jsonl(
        self, processor, mock_gmail_client, sample_config
    ):
        """メッセージがJSONLファイルに正しく保存されることを確認する。"""
        messages = [{"id": "msg_001", "threadId": "thread_001", "labelIds": ["INBOX"]}]
        result = processor.process_messages(messages)

        assert len(result) == 1
        jsonl_path = result[0]
        assert jsonl_path.name == "emails.jsonl"
        assert jsonl_path.exists()

        line = jsonl_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert record["message_id"] == "msg_001"
        assert record["sender"] == "target@example.com"
        assert record["subject"] == "テスト件名"
