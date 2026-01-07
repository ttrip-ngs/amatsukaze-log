"""設定モデル

YAMLファイルからの設定読み込みとバリデーション
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherConfig(BaseModel):
    """ログファイル監視設定"""

    log_directory: Path = Field(
        default=Path("/var/log/amatsukaze"), description="ログディレクトリパス"
    )
    file_pattern: str = Field(default="*.json", description="監視対象ファイルパターン")
    txt_wait_timeout: int = Field(default=30, description="TXTファイル待機時間（秒）")
    polling_interval: int = Field(default=5, description="ポーリング間隔（秒）")


class VectorWriterConfig(BaseModel):
    """Vector用ログファイル出力設定"""

    enabled: bool = Field(default=True, description="Vector用ログファイル出力有効化")
    log_directory: Path = Field(
        default=Path("/data/logs/vector"), description="ログファイル出力ディレクトリ"
    )
    rotate_size: int = Field(default=104857600, description="ローテーションサイズ（バイト）")


class SyslogWriterConfig(BaseModel):
    """rsyslogd用ログファイル出力設定"""

    enabled: bool = Field(default=True, description="syslog用ログファイル出力有効化")
    log_directory: Path = Field(
        default=Path("/data/logs/syslog"), description="ログファイル出力ディレクトリ"
    )
    rotate_size: int = Field(default=104857600, description="ローテーションサイズ（バイト）")


class DatabaseConfig(BaseModel):
    """処理済みログ管理DB設定"""

    path: Path = Field(default=Path("/data/processed_logs.db"), description="DBファイルパス")


class WriterConfig(BaseModel):
    """ログ書き込み設定"""

    vector: VectorWriterConfig = Field(default_factory=VectorWriterConfig)
    syslog: SyslogWriterConfig = Field(default_factory=SyslogWriterConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)


class CriticalRule(BaseModel):
    """CRITICAL判定ルール"""

    name: str = Field(description="ルール名")
    type: Literal["pattern", "condition"] = Field(description="ルールタイプ")
    pattern: str | None = Field(default=None, description="正規表現パターン（type=patternの場合）")
    condition: str | None = Field(
        default=None, description="条件式（type=conditionの場合）"
    )
    case_sensitive: bool = Field(default=True, description="大文字小文字を区別（patternの場合）")
    enabled: bool = Field(default=True, description="ルール有効化")
    message: str | None = Field(default=None, description="カスタムメッセージ")


class ParserConfig(BaseModel):
    """ログパーサー設定"""

    encoding: str = Field(default="utf-8-sig", description="ファイルエンコーディング")
    max_log_lines: int = Field(default=10000, description="最大ログ行数")
    critical_rules: list[CriticalRule] = Field(
        default_factory=list, description="CRITICAL判定ルール"
    )


class LoggingConfig(BaseModel):
    """ロギング設定"""

    level: str = Field(default="INFO", description="ログレベル")
    format: Literal["text", "json"] = Field(default="json", description="ログフォーマット")
    output: Literal["stdout", "stderr"] = Field(default="stdout", description="出力先")


class AppConfig(BaseModel):
    """アプリケーション設定"""

    worker_threads: int = Field(default=2, description="並列処理数")
    queue_size: int = Field(default=100, description="処理キューサイズ")


class Config(BaseSettings):
    """全体設定

    環境変数からの読み込みもサポート
    """

    watcher: WatcherConfig = Field(default_factory=WatcherConfig)
    writer: WriterConfig = Field(default_factory=WriterConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    # 環境変数
    environment: str = Field(default="production", description="実行環境")
    log_level: str = Field(default="INFO", description="ログレベル（環境変数）")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @classmethod
    def from_yaml(cls, config_path: Path) -> "Config":
        """YAMLファイルから設定読み込み

        Args:
            config_path: 設定ファイルパス

        Returns:
            Config: 設定オブジェクト

        Raises:
            FileNotFoundError: 設定ファイルが存在しない
            yaml.YAMLError: YAML解析エラー
        """
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    def validate_paths(self) -> None:
        """パスのバリデーション

        必要なディレクトリの存在確認と作成
        """
        # ログディレクトリの存在確認
        if not self.watcher.log_directory.exists():
            raise FileNotFoundError(
                f"ログディレクトリが存在しません: {self.watcher.log_directory}"
            )

        # 出力ディレクトリの作成
        if self.writer.vector.enabled:
            self.writer.vector.log_directory.mkdir(parents=True, exist_ok=True)
        if self.writer.syslog.enabled:
            self.writer.syslog.log_directory.mkdir(parents=True, exist_ok=True)

        # DBディレクトリの作成
        db_dir = self.writer.database.path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
