"""ログ送信機能のユニットテスト"""

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from src.collector.sender import LogSender, SyslogSender, VectorSender
from src.models.log_entry import IntegratedLogEntry, LokiLabels


@pytest.fixture
def sample_integrated_log() -> IntegratedLogEntry:
    """テスト用の統合ログデータ"""
    return IntegratedLogEntry(
        task_id="2025-10-18_120000.000",
        timestamp=datetime.now(timezone.utc),
        message="エンコード完了: テスト番組",
        program_name="テスト番組",
        labels=LokiLabels(
            service="amatsukaze",
            environment="test",
            host="test-host",
            status="success",
            severity="info",
            encoder="QSVEnc",
        ),
        src_path="/test/input.ts",
        out_path="/test/output.mp4",
        src_duration=3600.0,
        out_duration=3000.0,
        duration_diff=600.0,
        src_filesize=1000000,
        out_filesize=500000,
        compression_ratio=2.0,
        encoder="QSVEnc",
        format="Matroska",
        error_message=None,
        error_counts={"warn": 0, "error": 0, "info": 0, "debug": 0},
        phases={},
        command_line="test command",
    )


@pytest.mark.unit
class TestVectorSender:
    """VectorSender のテスト"""

    def test_send_success(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """正常な送信テスト"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.Client.post", return_value=mock_response) as mock_post:
            sender = VectorSender(endpoint="http://localhost:9000/logs")
            result = sender.send(sample_integrated_log)

            assert result is True
            mock_post.assert_called_once()

            # 送信データの検証
            call_kwargs = mock_post.call_args.kwargs
            payload = call_kwargs["json"]
            assert payload["task_id"] == "2025-10-18_120000.000"
            assert payload["program_name"] == "テスト番組"
            assert payload["labels"]["status"] == "success"
            assert payload["labels"]["severity"] == "info"

    def test_send_http_error(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """HTTPエラー時のテスト"""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=Mock(), response=mock_response
        )

        with patch("httpx.Client.post", return_value=mock_response):
            sender = VectorSender(endpoint="http://localhost:9000/logs")

            with pytest.raises(httpx.HTTPStatusError):
                sender.send(sample_integrated_log)

    def test_send_timeout(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """タイムアウト時のテスト"""
        with patch(
            "httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")
        ):
            sender = VectorSender(endpoint="http://localhost:9000/logs", timeout=1)

            with pytest.raises(httpx.TimeoutException):
                sender.send(sample_integrated_log)

    def test_json_payload_format(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """送信JSONフォーマットのテスト"""
        sender = VectorSender(endpoint="http://localhost:9000/logs")
        payload = sender._to_json(sample_integrated_log)

        # 必須フィールドの検証
        assert "timestamp" in payload
        assert "message" in payload
        assert "labels" in payload
        assert "task_id" in payload
        assert "program_name" in payload

        # Labels構造の検証
        labels = payload["labels"]
        assert labels["service"] == "amatsukaze"
        assert labels["status"] == "success"
        assert labels["severity"] == "info"

        # 数値フィールドの検証
        assert payload["compression_ratio"] == 2.0
        assert payload["src_filesize"] == 1000000
        assert payload["out_filesize"] == 500000

    def test_close(self) -> None:
        """クライアントクローズのテスト"""
        sender = VectorSender(endpoint="http://localhost:9000/logs")
        sender.close()
        # close()後は新しいリクエストを受け付けない
        assert sender.client.is_closed


@pytest.mark.unit
class TestSyslogSender:
    """SyslogSender のテスト"""

    def test_send_critical_log_udp(
        self, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL ログのUDP送信テスト"""
        # CRITICALに変更
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "重大なエラー"

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            # コンテキストマネージャーとして動作するようにする
            mock_socket.__enter__ = MagicMock(return_value=mock_socket)
            mock_socket.__exit__ = MagicMock(return_value=False)
            mock_socket_class.return_value = mock_socket

            sender = SyslogSender(host="localhost", port=514, protocol="udp")
            result = sender.send(sample_integrated_log)

            assert result is True
            mock_socket.sendto.assert_called_once()

            # 送信メッセージの検証
            sent_message = mock_socket.sendto.call_args[0][0].decode("utf-8")
            assert "CRITICAL" in sent_message
            assert "テスト番組" in sent_message
            assert "重大なエラー" in sent_message
            assert "<11>" in sent_message  # Priority: (1 << 3) | 3 = 11

    def test_send_critical_log_tcp(
        self, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL ログのTCP送信テスト"""
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "重大なエラー"

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            # コンテキストマネージャーとして動作するようにする
            mock_socket.__enter__ = MagicMock(return_value=mock_socket)
            mock_socket.__exit__ = MagicMock(return_value=False)
            mock_socket_class.return_value = mock_socket

            sender = SyslogSender(host="localhost", port=514, protocol="tcp")
            result = sender.send(sample_integrated_log)

            assert result is True
            mock_socket.connect.assert_called_once_with(("localhost", 514))
            mock_socket.sendall.assert_called_once()

            # 送信メッセージの検証（TCP: <length> + message）
            sent_data = mock_socket.sendall.call_args[0][0]
            message = sent_data.decode("utf-8")
            assert "CRITICAL" in message
            assert "テスト番組" in message

    def test_send_non_critical_log(
        self, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL以外のログは送信しないテスト"""
        # severity = "info" のまま
        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket_class.return_value = mock_socket

            sender = SyslogSender(host="localhost", port=514)
            result = sender.send(sample_integrated_log)

            # 送信はスキップされるがTrueを返す
            assert result is True
            mock_socket.sendto.assert_not_called()

    def test_syslog_message_format(
        self, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """syslogメッセージフォーマットのテスト"""
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "テストエラー"

        sender = SyslogSender(host="localhost", port=514)
        message = sender._format_syslog_message(sample_integrated_log)

        # RFC 3164形式: <Priority>Timestamp Hostname Tag: Message
        assert message.startswith("<11>")  # Priority
        assert "amatsukaze:" in message  # Tag
        assert "CRITICAL: [テスト番組] - テストエラー" in message

    def test_send_udp_error(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """UDP送信エラー時のテスト"""
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "エラー"

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket.__enter__ = MagicMock(return_value=mock_socket)
            mock_socket.__exit__ = MagicMock(return_value=False)
            mock_socket.sendto.side_effect = socket.error("Network error")
            mock_socket_class.return_value = mock_socket

            sender = SyslogSender(host="localhost", port=514, protocol="udp")

            with pytest.raises(OSError):
                sender.send(sample_integrated_log)

    def test_send_tcp_error(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """TCP送信エラー時のテスト"""
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "エラー"

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket.__enter__ = MagicMock(return_value=mock_socket)
            mock_socket.__exit__ = MagicMock(return_value=False)
            mock_socket.connect.side_effect = socket.error("Connection refused")
            mock_socket_class.return_value = mock_socket

            sender = SyslogSender(host="localhost", port=514, protocol="tcp")

            with pytest.raises(OSError):
                sender.send(sample_integrated_log)


@pytest.mark.unit
class TestLogSender:
    """LogSender のテスト"""

    def test_send_success_both(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """Vector/Syslog両方の送信成功テスト"""
        vector_sender = VectorSender(endpoint="http://localhost:9000")
        syslog_sender = SyslogSender(host="localhost", port=514)

        with patch.object(vector_sender, "send", return_value=True) as mock_vector, patch.object(
            syslog_sender, "send", return_value=True
        ) as mock_syslog:
            sender = LogSender(
                vector_sender=vector_sender,
                syslog_sender=syslog_sender,
            )

            vector_ok, syslog_ok = sender.send(sample_integrated_log)

            assert vector_ok is True
            assert syslog_ok is True
            mock_vector.assert_called_once_with(sample_integrated_log)
            mock_syslog.assert_called_once_with(sample_integrated_log)

    def test_send_vector_fail(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """Vector送信失敗テスト"""
        vector_sender = VectorSender(endpoint="http://localhost:9000")
        syslog_sender = SyslogSender(host="localhost", port=514)

        with patch.object(
            vector_sender, "send", side_effect=httpx.HTTPError("Error")
        ) as mock_vector, patch.object(
            syslog_sender, "send", return_value=True
        ) as mock_syslog:
            sender = LogSender(
                vector_sender=vector_sender,
                syslog_sender=syslog_sender,
            )

            vector_ok, syslog_ok = sender.send(sample_integrated_log)

            assert vector_ok is False
            assert syslog_ok is True
            mock_vector.assert_called_once()
            mock_syslog.assert_called_once()

    def test_send_syslog_fail(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """Syslog送信失敗テスト"""
        vector_sender = VectorSender(endpoint="http://localhost:9000")
        syslog_sender = SyslogSender(host="localhost", port=514)

        with patch.object(vector_sender, "send", return_value=True) as mock_vector, patch.object(
            syslog_sender, "send", side_effect=RuntimeError("Error")
        ) as mock_syslog:
            sender = LogSender(
                vector_sender=vector_sender,
                syslog_sender=syslog_sender,
            )

            vector_ok, syslog_ok = sender.send(sample_integrated_log)

            assert vector_ok is True
            assert syslog_ok is False
            mock_vector.assert_called_once()
            mock_syslog.assert_called_once()

    def test_send_both_fail(self, sample_integrated_log: IntegratedLogEntry) -> None:
        """両方の送信失敗テスト"""
        vector_sender = VectorSender(endpoint="http://localhost:9000")
        syslog_sender = SyslogSender(host="localhost", port=514)

        with patch.object(
            vector_sender, "send", side_effect=httpx.HTTPError("Error")
        ), patch.object(syslog_sender, "send", side_effect=RuntimeError("Error")):
            sender = LogSender(
                vector_sender=vector_sender,
                syslog_sender=syslog_sender,
            )

            vector_ok, syslog_ok = sender.send(sample_integrated_log)

            assert vector_ok is False
            assert syslog_ok is False

    def test_close(self) -> None:
        """リソースクローズのテスト"""
        vector_sender = VectorSender(endpoint="http://localhost:9000")

        with patch.object(vector_sender, "close") as mock_vector_close:
            sender = LogSender(vector_sender=vector_sender)
            sender.close()

            mock_vector_close.assert_called_once()
