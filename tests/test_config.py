"""config モジュールのテスト"""

import pytest
import yaml

from gmail_automation.config import load_config, generate_config_template


class TestLoadConfig:
    """load_config関数のテスト"""

    def test_load_config_success(self, tmp_path):
        """正常なconfig.yamlを読み込めることを確認する。"""
        config_data = {
            "gmail": {
                "target_senders": ["user@example.com"],
                "unread_only": True,
            },
            "pubsub": {
                "project_id": "my-project",
            },
            "output": {
                "directory": "./out",
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(config_data, allow_unicode=True),
            encoding="utf-8",
        )

        result = load_config(config_file)

        assert result.pubsub.project_id == "my-project"
        assert result.gmail.target_senders == ["user@example.com"]
        assert result.gmail.unread_only is True

    def test_load_config_file_not_found(self, tmp_path):
        """存在しないファイルを指定するとFileNotFoundErrorが発生する。"""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_config_invalid_yaml(self, tmp_path):
        """不正なYAML内容でエラーが発生する。"""
        config_file = tmp_path / "bad.yaml"
        # 空ファイルはsafe_loadでNoneを返すのでValueErrorになる
        config_file.write_text("", encoding="utf-8")

        with pytest.raises((yaml.YAMLError, ValueError)):
            load_config(config_file)


class TestGenerateConfigTemplate:
    """generate_config_template関数のテスト"""

    def test_generate_config_template(self):
        """テンプレート生成が空でないYAML文字列を返すことを確認する。"""
        template = generate_config_template()

        assert isinstance(template, str)
        assert len(template) > 0
        # YAMLとしてパース可能であることを確認
        parsed = yaml.safe_load(template)
        assert "gmail" in parsed
        assert "pubsub" in parsed
