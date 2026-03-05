"""HTML/テキスト→PDF変換モジュール。

WeasyPrintを使用してHTMLまたはプレーンテキストをPDFに変換する。
"""

import re
import html
from pathlib import Path

from weasyprint import HTML


# ファイル名に使用できない文字のパターン
_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# ファイル名の最大長
_MAX_FILENAME_LENGTH = 100

# 日本語フォントを含むCSS
_BASE_CSS = """\
@page {
    size: A4;
    margin: 20mm;
}
body {
    font-family: "Noto Sans JP", "Hiragino Sans", "Hiragino Kaku Gothic ProN", sans-serif;
    font-size: 12pt;
    line-height: 1.8;
    color: #333;
}
"""


def text_to_html(text: str) -> str:
    """プレーンテキストをHTMLに変換する。

    改行を<br>タグに変換し、HTMLエスケープを適用する。

    Args:
        text: 変換対象のプレーンテキスト。

    Returns:
        HTML文字列。
    """
    escaped = html.escape(text)
    return escaped.replace("\n", "<br>\n")


def wrap_html_with_style(html_content: str) -> str:
    """HTMLにCSSスタイルを付与する。

    日本語フォント指定・A4サイズ対応・余白設定などのスタイルを
    HTMLに適用したラッパーを返す。

    Args:
        html_content: スタイルを付与するHTML本文。

    Returns:
        CSSスタイル付きの完全なHTMLドキュメント。
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ja">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<style>{_BASE_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{html_content}\n"
        "</body>\n"
        "</html>"
    )


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
        安全なファイル名文字列（.pdf拡張子なし）。
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


def convert_to_pdf(
    html_content: str | None,
    text_content: str | None,
    output_path: Path,
) -> Path:
    """HTMLまたはテキストコンテンツをPDFに変換して保存する。

    HTMLコンテンツが提供されている場合はそれを使用し、
    なければテキストコンテンツからHTMLを生成してPDFに変換する。

    Args:
        html_content: HTML形式のコンテンツ。Noneの場合はtext_contentを使用。
        text_content: プレーンテキスト形式のコンテンツ。html_contentがNoneの場合に使用。
        output_path: PDF出力先のファイルパス。

    Returns:
        保存されたPDFファイルのパス。

    Raises:
        ValueError: html_contentとtext_contentの両方がNoneの場合。
    """
    if html_content is None and text_content is None:
        raise ValueError(
            "html_contentまたはtext_contentのいずれかを指定してください"
        )

    if html_content is not None:
        styled_html = wrap_html_with_style(html_content)
    else:
        # text_contentは上のバリデーションによりNoneでないことが保証されている
        body_html = text_to_html(text_content)  # type: ignore[arg-type]
        styled_html = wrap_html_with_style(body_html)

    # 出力ディレクトリが存在しない場合は作成
    output_path.parent.mkdir(parents=True, exist_ok=True)

    HTML(string=styled_html).write_pdf(output_path)

    return output_path
