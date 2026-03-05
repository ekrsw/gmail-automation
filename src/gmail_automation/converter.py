"""メールデータ変換モジュール。

メールメッセージからJSONLレコードを構築し、ファイルに追記する。
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ファイル名に使用できない文字のパターン
_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# ファイル名の最大長
_MAX_FILENAME_LENGTH = 100


def generate_filename(
    date_str: str, sender: str, subject: str, template: str
) -> str:
    """テンプレートに基づいてファイル名を生成する。

    テンプレート内の {date}、{sender}、{subject} を置換し、
    ファイル名に使用できない文字を除去する。

    Args:
        date_str: 日付文字列。
        sender: 送信者名またはメールアドレス。
        subject: メールの件名。
        template: ファイル名テンプレート（例: "{date}_{sender}_{subject}"）。

    Returns:
        安全なファイル名文字列。
    """
    filename = template.format(
        date=date_str,
        sender=sender,
        subject=subject,
    )

    # ファイル名に使えない文字をアンダースコアに置換
    filename = _INVALID_FILENAME_CHARS.sub("_", filename)

    # 連続するアンダースコアを1つにまとめる
    filename = re.sub(r"_+", "_", filename)

    # 前後の空白・アンダースコアを除去
    filename = filename.strip(" _")

    # 最大長を超える場合は切り詰める
    if len(filename) > _MAX_FILENAME_LENGTH:
        filename = filename[:_MAX_FILENAME_LENGTH].rstrip(" _")

    return filename


def build_mail_record(
    message: dict,
    sender: str,
    subject: str,
    date_str: str,
    html_body: str | None,
    text_body: str | None,
) -> dict:
    """メールメッセージからJSONLレコード用の辞書を構築する。

    Args:
        message: Gmail APIのメッセージ辞書。
        sender: 送信者メールアドレス。
        subject: メールの件名。
        date_str: 日付文字列。
        html_body: HTML形式の本文。
        text_body: プレーンテキスト形式の本文。

    Returns:
        JSONLレコード用の辞書。
    """
    return {
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
        "sender": sender,
        "subject": subject,
        "date": date_str,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "html_body": html_body or "",
        "text_body": text_body or "",
        "labels": message.get("labelIds", []),
    }


def append_to_jsonl(record: dict, output_path: Path) -> Path:
    """レコードをJSONLファイルに追記する。

    Args:
        record: 追記するレコード辞書。
        output_path: JSONLファイルのパス。

    Returns:
        出力ファイルのパス。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return output_path
