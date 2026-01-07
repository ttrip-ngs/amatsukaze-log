"""テスト共通設定"""

import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_log_dir() -> Path:
    """サンプルログディレクトリ

    コンテナ内とローカル環境の両方に対応
    """
    # 環境変数でオーバーライド可能
    env_path = os.environ.get("SAMPLE_LOG_DIR")
    if env_path:
        return Path(env_path)

    # コンテナ内の場合（/var/log/amatsukaze）
    container_path = Path("/var/log/amatsukaze")
    if container_path.exists():
        return container_path

    # ローカル環境の場合（tmp/sample_log）
    local_path = Path("tmp/sample_log")
    if local_path.exists():
        return local_path

    # プロジェクトルートからの相対パス
    project_root = Path(__file__).parent.parent
    return project_root / "tmp" / "sample_log"
