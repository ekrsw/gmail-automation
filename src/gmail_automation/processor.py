"""メール処理パイプラインモジュール

メールの取得・フィルタリング・JSONL保存を行うパイプラインを提供する。
処理済みメッセージの重複排除機能を含む。
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gmail_automation.config import AppConfig
from gmail_automation.converter import append_to_jsonl, build_mail_record
from gmail_automation.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class ProcessedIdStore:
    """処理済みメッセージIDの永続化ストア

    JSONファイルを用いて処理済みメッセージIDを管理し、
    重複処理を防止する。
    """

    def __init__(self, store_path: Path = Path("credentials/processed_ids.json")) -> None:
        """処理済みIDストアを初期化する。

        Args:
            store_path: 処理済みIDを保存するJSONファイルのパス。
        """
        self._store_path = store_path

    def load(self) -> set[str]:
        """処理済みメッセージIDをセットとして読み込む。

        Returns:
            処理済みメッセージIDのセット。ファイルが存在しない場合は空セット。
        """
        if not self._store_path.exists():
            return set()

        with self._store_path.open(encoding="utf-8") as f:
            data = json.load(f)

        return set(data)

    def save(self, ids: set[str]) -> None:
        """処理済みIDをJSONファイルに保存する。

        Args:
            ids: 保存する処理済みメッセージIDのセット。
        """
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

        with self._store_path.open("w", encoding="utf-8") as f:
            json.dump(sorted(ids), f, ensure_ascii=False, indent=2)

    def is_processed(self, message_id: str) -> bool:
        """指定されたメッセージIDが処理済みか判定する。

        Args:
            message_id: 判定対象のメッセージID。

        Returns:
            処理済みの場合True。
        """
        return message_id in self.load()

    def clear(self) -> None:
        """処理済みIDストアをクリアする。"""
        if self._store_path.exists():
            self._store_path.unlink()

    def mark_processed(self, message_id: str) -> None:
        """指定されたメッセージIDを処理済みとしてマークする。

        Args:
            message_id: 処理済みにするメッセージID。
        """
        ids = self.load()
        ids.add(message_id)
        self.save(ids)


class MailProcessor:
    """メール処理パイプライン

    メールの取得・フィルタリング・JSONL保存を一括で行う。
    """

    def __init__(self, config: AppConfig, gmail_client: GmailClient) -> None:
        """メール処理パイプラインを初期化する。

        Args:
            config: アプリケーション設定。
            gmail_client: Gmail APIクライアント。
        """
        self._config = config
        self._gmail_client = gmail_client
        store_path = config.auth.credentials_file.parent / "processed_ids.json"
        self._id_store = ProcessedIdStore(store_path=store_path)

    def clear_processed_ids(self) -> None:
        """処理済みIDストアをクリアする。"""
        self._id_store.clear()

    def process_messages(self, messages: list[dict]) -> list[Path]:
        """メッセージリストを処理してJSONLに保存する。

        差出人フィルタ・重複チェックを行い、メールデータをJSONLに追記する。

        Args:
            messages: 処理対象のメッセージ辞書のリスト。

        Returns:
            保存先のJSONLファイルパスのリスト（保存した場合は1要素）。
        """
        output_dir = Path(self._config.output.directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = output_dir / "emails.jsonl"

        target_senders = {s.lower() for s in self._config.gmail.target_senders}
        results: list[Path] = []

        for message in messages:
            message_id = message.get("id", "")

            # 重複チェック
            if self._id_store.is_processed(message_id):
                logger.debug("スキップ（処理済み）: メッセージID=%s", message_id)
                continue

            # 差出人フィルタ
            sender = self._gmail_client.extract_sender(message)
            sender_email = self._parse_email_address(sender)
            if sender_email.lower() not in target_senders:
                logger.debug(
                    "スキップ（対象外の差出人）: sender=%s, メッセージID=%s",
                    sender,
                    message_id,
                )
                continue

            # 本文抽出
            html_body, text_body = self._gmail_client.extract_body(message)
            if not html_body and not text_body:
                logger.warning("本文が空です: メッセージID=%s", message_id)
                continue

            # メタデータ取得
            date_str = self._gmail_client.extract_date(message)
            subject = self._gmail_client.extract_subject(message)

            # JSONLレコード構築・追記
            record = build_mail_record(
                message=message,
                sender=sender_email,
                subject=subject,
                date_str=date_str,
                html_body=html_body or None,
                text_body=text_body or None,
            )
            append_to_jsonl(record, jsonl_path)

            # 処理済みマーク
            self._id_store.mark_processed(message_id)
            results.append(jsonl_path)
            logger.info("JSONL保存完了: メッセージID=%s", message_id)

        return results

    def fetch_and_process(
        self,
        days: int = 7,
        after: str | None = None,
        before: str | None = None,
    ) -> list[Path]:
        """メールを取得して処理する。

        after/beforeが指定された場合は日付範囲で取得し、
        指定されない場合は過去N日分を取得する。

        Args:
            days: 取得対象の日数。after/before未指定時に使用。デフォルトは7日。
            after: 取得開始日（YYYY/MM/DD形式）。この日以降のメールを取得。
            before: 取得終了日（YYYY/MM/DD形式）。この日以前のメールを取得。

        Returns:
            保存先のJSONLファイルパスのリスト。
        """
        if after or before:
            parts: list[str] = []
            if after:
                parts.append(f"after:{after}")
            if before:
                parts.append(f"before:{before}")
            date_query = " ".join(parts)
        else:
            after_date = datetime.now(tz=timezone.utc) - timedelta(days=days)
            date_query = f"after:{after_date.strftime('%Y/%m/%d')}"
        logger.info("メール取得開始: query=%s", date_query)

        all_messages: list[dict] = []
        for sender in self._config.gmail.target_senders:
            messages = self._gmail_client.fetch_messages(
                query=f"from:{sender} {date_query}",
            )
            logger.info("取得件数: sender=%s, count=%d", sender, len(messages))
            all_messages.extend(messages)

        return self.process_messages(all_messages)

    def process_history(self, history_id: str) -> list[Path]:
        """historyIdベースで新着メールを処理する。

        Args:
            history_id: Gmail APIのhistoryId。

        Returns:
            保存先のJSONLファイルパスのリスト。
        """
        logger.info("履歴ベースの処理開始: historyId=%s", history_id)

        added_messages = self._gmail_client.get_history(start_history_id=history_id)
        if not added_messages:
            logger.info("新着メッセージなし")
            return []

        logger.info("新着メッセージ数: %d", len(added_messages))

        # get_historyは部分的なメッセージ情報を返すので、詳細を取得する
        messages: list[dict] = []
        for msg in added_messages:
            msg_id = msg.get("id")
            if msg_id:
                detail = self._gmail_client.get_message_detail(message_id=msg_id)
                messages.append(detail)

        return self.process_messages(messages)

    @staticmethod
    def _parse_email_address(sender: str) -> str:
        """送信者文字列からメールアドレスを抽出する。

        Args:
            sender: 送信者文字列（例: "Name <email@example.com>" または "email@example.com"）

        Returns:
            メールアドレス。
        """
        if "<" in sender and ">" in sender:
            return sender.split("<")[1].split(">")[0]
        return sender
