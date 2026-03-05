"""converter モジュールのテスト"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gmail_automation.converter import (
    text_to_html,
    wrap_html_with_style,
    generate_filename,
    convert_to_pdf,
)


class TestTextToHtml:
    """text_to_html関数のテスト"""

    def test_text_to_html(self):
        """改行がbrタグに変換され、HTMLエスケープが適用される。"""
        text = "行1\n行2\n<script>alert('xss')</script>"

        result = text_to_html(text)

        assert "<br>" in result
        assert "&lt;script&gt;" in result
        assert "<script>" not in result


class TestWrapHtmlWithStyle:
    """wrap_html_with_style関数のテスト"""

    def test_wrap_html_with_style(self):
        """CSSスタイルを含む完全なHTMLドキュメントが生成される。"""
        content = "<p>テスト</p>"

        result = wrap_html_with_style(content)

        assert "<!DOCTYPE html>" in result
        assert '<html lang="ja">' in result
        assert "<style>" in result
        assert "Noto Sans JP" in result
        assert content in result


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


class TestConvertToPdf:
    """convert_to_pdf関数のテスト"""

    def test_convert_to_pdf(self, mocker, tmp_path):
        """WeasyPrintのwrite_pdfが正しく呼ばれることを確認する。"""
        mock_html_cls = mocker.patch("gmail_automation.converter.HTML")
        mock_instance = MagicMock()
        mock_html_cls.return_value = mock_instance

        output_path = tmp_path / "test.pdf"

        result = convert_to_pdf(
            html_content="<p>テスト</p>",
            text_content=None,
            output_path=output_path,
        )

        mock_html_cls.assert_called_once()
        mock_instance.write_pdf.assert_called_once_with(output_path)
        assert result == output_path
