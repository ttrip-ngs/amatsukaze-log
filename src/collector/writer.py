"""ログファイル書き込みモジュール

解析済みログをJSON Lines形式でファイルに書き込み、Vectorで読み込ませる
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.models.log_entry import IntegratedLogEntry

logger = logging.getLogger(__name__)


class LogFileWriter:
    """ログファイルライター

    JSON Lines形式でログを書き込み、Vectorが読み込む
    """

    def __init__(
        self,
        log_dir: Path,
        rotate_size: int = 104857600,  # 100MB
        date_format: str = "%Y%m%d",
    ):
        """初期化

        Args:
            log_dir: ログ出力ディレクトリ
            rotate_size: ファイルローテーションサイズ（bytes）
            date_format: ファイル名の日付フォーマット
        """
        self.log_dir = Path(log_dir)
        self.rotate_size = rotate_size
        self.date_format = date_format

        # ログディレクトリ作成
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, log_data: IntegratedLogEntry) -> Path:
        """ログをJSON Lines形式でファイルに書き込み

        Args:
            log_data: 統合ログデータ

        Returns:
            Path: 書き込んだファイルパス

        Raises:
            OSError: ファイル書き込みエラー
        """
        # 日付ベースのファイル名
        date_str = datetime.now().strftime(self.date_format)
        log_file = self.log_dir / f"amatsukaze-{date_str}.jsonl"

        try:
            # JSON Lines形式で追記
            with log_file.open("a", encoding="utf-8") as f:
                json_line = json.dumps(
                    log_data.to_dict(), ensure_ascii=False, separators=(",", ":")
                )
                f.write(json_line + "\n")

            logger.info(f"ログ書き込み成功: {log_data.task_id} -> {log_file}")

            # ファイルサイズチェック＆ローテーション
            if log_file.stat().st_size > self.rotate_size:
                self._rotate(log_file)

            return log_file

        except OSError as e:
            logger.error(f"ログ書き込み失敗: {log_data.task_id} - {e}")
            raise

    def _rotate(self, log_file: Path) -> None:
        """ファイルローテーション

        Args:
            log_file: ローテーション対象ファイル
        """
        # タイムスタンプ付きファイル名に変更
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_file = log_file.with_name(f"{log_file.stem}_{timestamp}.jsonl")

        try:
            log_file.rename(rotated_file)
            logger.info(f"ファイルローテーション: {log_file} -> {rotated_file}")
        except OSError as e:
            logger.error(f"ファイルローテーション失敗: {log_file} - {e}")


class SyslogFileWriter:
    """Syslogファイルライター

    CRITICALログをsyslog形式でファイルに書き込み、rsyslogdが読み込む
    """

    # Syslog facility/severity
    FACILITY_USER = 1  # user-level messages
    SEVERITY_ERROR = 3  # error conditions
    PRIORITY = (FACILITY_USER << 3) | SEVERITY_ERROR  # 11

    def __init__(self, log_dir: Path):
        """初期化

        Args:
            log_dir: ログ出力ディレクトリ
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, log_data: IntegratedLogEntry) -> Path | None:
        """CRITICALログをsyslog形式でファイルに書き込み

        Args:
            log_data: 統合ログデータ

        Returns:
            Path | None: 書き込んだファイルパス（CRITICALでない場合None）

        Raises:
            OSError: ファイル書き込みエラー
        """
        # CRITICALでない場合は書き込まない
        if log_data.labels.severity != "critical":
            logger.debug(f"CRITICAL以外のため書き込みスキップ: {log_data.task_id}")
            return None

        # 日付ベースのファイル名
        date_str = datetime.now().strftime("%Y%m%d")
        log_file = self.log_dir / f"amatsukaze-critical-{date_str}.log"

        try:
            # Syslog形式で追記
            message = self._format_syslog_message(log_data)
            with log_file.open("a", encoding="utf-8") as f:
                f.write(message + "\n")

            logger.info(f"CRITICALログ書き込み成功: {log_data.task_id} -> {log_file}")
            return log_file

        except OSError as e:
            logger.error(f"CRITICALログ書き込み失敗: {log_data.task_id} - {e}")
            raise

    def _format_syslog_message(self, log_data: IntegratedLogEntry) -> str:
        """Syslogメッセージをフォーマット

        Args:
            log_data: 統合ログデータ

        Returns:
            str: Syslogメッセージ（RFC 3164形式）
        """
        # RFC 3164形式: <Priority>Timestamp Hostname Tag: Message
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        hostname = log_data.labels.host
        tag = "amatsukaze"

        message_body = (
            f"CRITICAL: [{log_data.program_name}] - "
            f"{log_data.error_message or 'エンコード失敗'}"
        )

        return f"<{self.PRIORITY}>{timestamp} {hostname} {tag}: {message_body}"


class LogWriter:
    """ログライター統合クラス

    Vector用とSyslog用の両方にファイル書き込み
    """

    def __init__(
        self,
        vector_log_dir: Path | None = None,
        syslog_log_dir: Path | None = None,
        rotate_size: int = 104857600,  # 100MB
    ):
        """初期化

        Args:
            vector_log_dir: Vector用ログディレクトリ
            syslog_log_dir: Syslog用ログディレクトリ
            rotate_size: ファイルローテーションサイズ（bytes）
        """
        self.vector_writer = (
            LogFileWriter(vector_log_dir, rotate_size) if vector_log_dir else None
        )
        self.syslog_writer = (
            SyslogFileWriter(syslog_log_dir) if syslog_log_dir else None
        )

    def write(self, log_data: IntegratedLogEntry) -> tuple[Path | None, Path | None]:
        """ログを両方のファイルに書き込み

        Args:
            log_data: 統合ログデータ

        Returns:
            tuple[Path | None, Path | None]: (Vector用ファイルパス, Syslog用ファイルパス)
        """
        vector_path = None
        syslog_path = None

        # Vector用ファイル書き込み
        if self.vector_writer:
            try:
                vector_path = self.vector_writer.write(log_data)
            except OSError as e:
                logger.error(f"Vector用ファイル書き込みエラー: {e}", exc_info=True)

        # Syslog用ファイル書き込み（CRITICALのみ）
        if self.syslog_writer:
            try:
                syslog_path = self.syslog_writer.write(log_data)
            except OSError as e:
                logger.error(f"Syslog用ファイル書き込みエラー: {e}", exc_info=True)

        return vector_path, syslog_path
