"""ログ送信モジュール

解析済みログをVector（HTTP）とrsyslogd（syslog）に送信する
"""

import logging
import socket
from datetime import datetime, timezone
from typing import Any

import httpx

from src.models.log_entry import IntegratedLogEntry

logger = logging.getLogger(__name__)


class VectorSender:
    """Vector送信クラス

    解析済みログをVectorにHTTP POST（JSON）で送信
    """

    def __init__(
        self,
        endpoint: str,
        timeout: int = 10,
        retry_max: int = 5,
    ):
        """初期化

        Args:
            endpoint: VectorのHTTPエンドポイント
            timeout: タイムアウト（秒）
            retry_max: 最大リトライ回数
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.retry_max = retry_max
        self.client = httpx.Client(timeout=timeout)

    def send(self, log_data: IntegratedLogEntry) -> bool:
        """ログデータをVectorに送信

        Args:
            log_data: 統合ログデータ

        Returns:
            bool: 送信成功時True

        Raises:
            httpx.HTTPError: HTTP通信エラー
        """
        # JSON形式に変換
        payload = self._to_json(log_data)

        try:
            response = self.client.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            logger.info(f"Vector送信成功: {log_data.task_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Vector送信失敗: {log_data.task_id} - {e}")
            raise

    def _to_json(self, log_data: IntegratedLogEntry) -> dict[str, Any]:
        """ログデータをJSON形式に変換

        Args:
            log_data: 統合ログデータ

        Returns:
            dict: JSON形式のデータ
        """
        return {
            "timestamp": log_data.timestamp.isoformat(),
            "message": log_data.message,
            # Labels
            "labels": {
                "service": log_data.labels.service,
                "environment": log_data.labels.environment,
                "host": log_data.labels.host,
                "status": log_data.labels.status,
                "severity": log_data.labels.severity,
                "encoder": log_data.labels.encoder,
            },
            # Metadata
            "task_id": log_data.task_id,
            "program_name": log_data.program_name,
            "src_path": log_data.src_path,
            "src_duration": log_data.src_duration,
            "out_duration": log_data.out_duration,
            "src_filesize": log_data.src_filesize,
            "out_filesize": log_data.out_filesize,
            "compression_ratio": log_data.compression_ratio,
            "error_message": log_data.error_message,
            "error_counts": log_data.error_counts,
            "format": log_data.format,
        }

    def close(self) -> None:
        """クライアントをクローズ"""
        self.client.close()


class SyslogSender:
    """rsyslogd送信クラス

    CRITICALログをsyslogプロトコルで送信
    """

    # Syslog facility/severity
    FACILITY_USER = 1  # user-level messages
    SEVERITY_ERROR = 3  # error conditions
    PRIORITY = (FACILITY_USER << 3) | SEVERITY_ERROR  # 11

    def __init__(
        self,
        host: str = "localhost",
        port: int = 514,
        protocol: str = "udp",
    ):
        """初期化

        Args:
            host: rsyslogdホスト
            port: rsyslogdポート
            protocol: プロトコル（udp or tcp）
        """
        self.host = host
        self.port = port
        self.protocol = protocol.lower()

        if self.protocol not in ("udp", "tcp"):
            raise ValueError(f"不正なプロトコル: {protocol}")

    def send(self, log_data: IntegratedLogEntry) -> bool:
        """CRITICALログをsyslogに送信

        Args:
            log_data: 統合ログデータ

        Returns:
            bool: 送信成功時True

        Raises:
            OSError: ソケット通信エラー
        """
        # CRITICALでない場合は送信しない
        if log_data.labels.severity != "critical":
            logger.debug(f"CRITICAL以外のため送信スキップ: {log_data.task_id}")
            return True

        # Syslogメッセージを構築
        message = self._format_syslog_message(log_data)

        try:
            if self.protocol == "udp":
                self._send_udp(message)
            else:
                self._send_tcp(message)

            logger.info(f"syslog送信成功: {log_data.task_id}")
            return True

        except OSError as e:
            logger.error(f"syslog送信失敗: {log_data.task_id} - {e}")
            raise

    def _format_syslog_message(self, log_data: IntegratedLogEntry) -> str:
        """Syslogメッセージをフォーマット

        Args:
            log_data: 統合ログデータ

        Returns:
            str: Syslogメッセージ
        """
        # RFC 3164形式: <Priority>Timestamp Hostname Tag: Message
        timestamp = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
        hostname = socket.gethostname()
        tag = "amatsukaze"

        message_body = (
            f"CRITICAL: [{log_data.program_name}] - "
            f"{log_data.error_message or 'エンコード失敗'}"
        )

        return f"<{self.PRIORITY}>{timestamp} {hostname} {tag}: {message_body}"

    def _send_udp(self, message: str) -> None:
        """UDPでsyslog送信

        Args:
            message: Syslogメッセージ
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(message.encode("utf-8"), (self.host, self.port))

    def _send_tcp(self, message: str) -> None:
        """TCPでsyslog送信

        Args:
            message: Syslogメッセージ
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self.host, self.port))
            # RFC 6587: octet counting framing
            message_with_length = f"{len(message)} {message}"
            sock.sendall(message_with_length.encode("utf-8"))


class LogSender:
    """ログ送信統合クラス

    VectorとSyslogの両方に送信
    """

    def __init__(
        self,
        vector_sender: VectorSender | None = None,
        syslog_sender: SyslogSender | None = None,
    ):
        """初期化

        Args:
            vector_sender: Vector送信クラス
            syslog_sender: Syslog送信クラス
        """
        self.vector_sender = vector_sender
        self.syslog_sender = syslog_sender

    def send(self, log_data: IntegratedLogEntry) -> tuple[bool, bool]:
        """ログを送信

        Args:
            log_data: 統合ログデータ

        Returns:
            tuple[bool, bool]: (Vector送信結果, Syslog送信結果)
        """
        vector_success = True
        syslog_success = True

        # Vector送信
        if self.vector_sender:
            try:
                vector_success = self.vector_sender.send(log_data)
            except Exception as e:
                logger.error(f"Vector送信エラー: {e}", exc_info=True)
                vector_success = False

        # Syslog送信（CRITICALのみ）
        if self.syslog_sender:
            try:
                syslog_success = self.syslog_sender.send(log_data)
            except Exception as e:
                logger.error(f"Syslog送信エラー: {e}", exc_info=True)
                syslog_success = False

        return vector_success, syslog_success

    def close(self) -> None:
        """リソースをクローズ"""
        if self.vector_sender:
            self.vector_sender.close()
