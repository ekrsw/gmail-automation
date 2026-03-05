"""Pub/Sub Pull型リスナーモジュール。

Google Cloud Pub/Subを使用してGmailの変更通知を受信し、
メール処理パイプラインを駆動する。
"""

import json
import logging
import time

from google.cloud.pubsub_v1 import SubscriberClient

from gmail_automation.config import AppConfig
from gmail_automation.gmail_client import GmailClient
from gmail_automation.processor import MailProcessor

logger = logging.getLogger(__name__)

# watch有効期限の更新猶予（1時間 = 3600秒）
_WATCH_RENEWAL_MARGIN_SECONDS = 3600


class PubSubListener:
    """Pub/Sub Pull型リスナー。

    Gmail APIのwatch機能とCloud Pub/Subを連携させ、
    メール受信イベントをリアルタイムに処理する。
    """

    def __init__(
        self,
        config: AppConfig,
        gmail_client: GmailClient,
        processor: MailProcessor,
    ) -> None:
        """リスナーを初期化する。

        Args:
            config: アプリケーション設定。
            gmail_client: Gmail APIクライアント。
            processor: メール処理プロセッサ。
        """
        self._config = config
        self._gmail_client = gmail_client
        self._processor = processor

        self._subscriber = SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(
            config.pubsub.project_id,
            config.pubsub.subscription_name,
        )

        self._last_history_id: str | None = None
        self._watch_expiration: float | None = None

    def setup_watch(self) -> None:
        """Gmail APIにPub/Sub通知を登録する。

        watchレスポンスからhistoryIdとexpirationを保存し、
        以降の変更検出に使用する。
        """
        topic_name = (
            f"projects/{self._config.pubsub.project_id}"
            f"/topics/{self._config.pubsub.topic_name}"
        )
        response = self._gmail_client.watch(topic_name)

        self._last_history_id = response["historyId"]
        # expirationはミリ秒のため秒に変換する
        self._watch_expiration = int(response["expiration"]) / 1000.0

        logger.info(
            "watch登録完了: historyId=%s, expiration=%s",
            self._last_history_id,
            self._watch_expiration,
        )

    def _should_renew_watch(self) -> bool:
        """watchの有効期限更新が必要かどうかを判定する。

        有効期限の1時間前に達した場合にTrueを返す。

        Returns:
            更新が必要な場合はTrue。
        """
        if self._watch_expiration is None:
            return True
        return time.time() >= self._watch_expiration - _WATCH_RENEWAL_MARGIN_SECONDS

    def _handle_message(self, message) -> None:  # noqa: ANN001
        """Pub/Subメッセージを処理する。

        受信したメッセージからhistoryIdを取得し、
        対応するメール変更をプロセッサに渡す。

        Args:
            message: Pub/Subから受信したメッセージ。
        """
        try:
            data = json.loads(message.data.decode("utf-8"))
            email_address = data.get("emailAddress")
            history_id = data.get("historyId")

            logger.info(
                "Pub/Subメッセージ受信: emailAddress=%s, historyId=%s",
                email_address,
                history_id,
            )

            if self._last_history_id and history_id:
                self._processor.process_history(self._last_history_id)
                self._last_history_id = history_id

        finally:
            message.ack()

        # watchの有効期限チェックと必要に応じた更新
        if self._should_renew_watch():
            logger.info("watchの有効期限が近いため再登録します")
            self.setup_watch()

    def start(self) -> None:
        """Pub/Sub監視を開始する。

        サブスクリプションからメッセージをPull受信し、
        コールバックで処理を行う。KeyboardInterruptで停止する。
        """
        self.setup_watch()

        streaming_pull_future = self._subscriber.subscribe(
            self._subscription_path,
            callback=self._handle_message,
        )
        logger.info("Pub/Sub監視を開始しました")

        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            logger.info("Pub/Sub監視を停止しました")
