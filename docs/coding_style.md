# Coding Style Guide

## Python

### パッケージ管理

- パッケージマネージャーには `uv` を使用する。
- `uv venv` で仮想環境を構築し、仮想環境を有効化してから作業すること。

```bash
# 仮想環境の構築
uv venv

# 仮想環境の有効化
source .venv/bin/activate

# パッケージのインストール
uv pip install <package>
```
