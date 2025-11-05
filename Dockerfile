# Amatsukaze Log Collector Dockerfile
FROM python:3.13-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージ更新
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をコピーしてインストール
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"

# 設定ファイルとテストをコピー
COPY config ./config
COPY tests ./tests

# 開発用: ホットリロード対応
ENV PYTHONUNBUFFERED=1

# ヘルスチェック用ポート公開（将来実装）
EXPOSE 8000

# デフォルトコマンド（開発時はdocker-compose.dev.ymlで上書き）
CMD ["python", "-m", "src.main"]
