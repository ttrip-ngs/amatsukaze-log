"""ログファイル書き込み機能のユニットテスト"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.collector.writer import LogFileWriter, LogWriter, SyslogFileWriter
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
class TestLogFileWriter:
    """LogFileWriter のテスト"""

    def test_write_success(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """正常な書き込みテスト"""
        log_dir = tmp_path / "logs"
        writer = LogFileWriter(log_dir)

        result = writer.write(sample_integrated_log)

        # ファイルが作成されている
        assert result.exists()
        assert result.suffix == ".jsonl"

        # ファイル内容確認
        with result.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1

            log_data = json.loads(lines[0])
            assert log_data["task_id"] == "2025-10-18_120000.000"
            assert log_data["program_name"] == "テスト番組"
            assert log_data["labels"]["status"] == "success"

    def test_write_multiple(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """複数書き込みテスト"""
        log_dir = tmp_path / "logs"
        writer = LogFileWriter(log_dir)

        # 3件書き込み
        result1 = writer.write(sample_integrated_log)
        result2 = writer.write(sample_integrated_log)
        result3 = writer.write(sample_integrated_log)

        # 同じファイルに追記される
        assert result1 == result2 == result3

        # 3行になっている
        with result1.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 3

    def test_rotate(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """ファイルローテーションテスト"""
        log_dir = tmp_path / "logs"
        writer = LogFileWriter(log_dir, rotate_size=100)  # 100bytesで小さく設定

        # 複数回書き込み（ローテーション発生）
        first_file = writer.write(sample_integrated_log)
        writer.write(sample_integrated_log)
        writer.write(sample_integrated_log)

        # ローテーションされたファイルが存在
        rotated_files = list(log_dir.glob("amatsukaze-*_*.jsonl"))
        assert len(rotated_files) > 0

    def test_json_format(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """JSON Lines形式のテスト"""
        log_dir = tmp_path / "logs"
        writer = LogFileWriter(log_dir)

        result = writer.write(sample_integrated_log)

        # JSON Lines形式で読み込める
        with result.open("r", encoding="utf-8") as f:
            for line in f:
                log_data = json.loads(line)
                assert "task_id" in log_data
                assert "timestamp" in log_data
                assert "labels" in log_data


@pytest.mark.unit
class TestSyslogFileWriter:
    """SyslogFileWriter のテスト"""

    def test_write_critical_log(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL ログの書き込みテスト"""
        log_dir = tmp_path / "logs"
        writer = SyslogFileWriter(log_dir)

        # CRITICALに変更
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "重大なエラー"

        result = writer.write(sample_integrated_log)

        # ファイルが作成されている
        assert result is not None
        assert result.exists()
        assert "critical" in result.name

        # ファイル内容確認（syslog形式）
        with result.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1

            syslog_message = lines[0].strip()
            assert "<11>" in syslog_message  # Priority
            assert "CRITICAL" in syslog_message
            assert "テスト番組" in syslog_message
            assert "重大なエラー" in syslog_message

    def test_skip_non_critical_log(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL以外のログはスキップテスト"""
        log_dir = tmp_path / "logs"
        writer = SyslogFileWriter(log_dir)

        # severity = "info" のまま
        result = writer.write(sample_integrated_log)

        # ファイルは作成されない
        assert result is None

        # ディレクトリにファイルが存在しない
        assert len(list(log_dir.glob("*.log"))) == 0

    def test_syslog_format(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """syslogメッセージフォーマットのテスト"""
        log_dir = tmp_path / "logs"
        writer = SyslogFileWriter(log_dir)

        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "テストエラー"

        message = writer._format_syslog_message(sample_integrated_log)

        # RFC 3164形式
        assert message.startswith("<11>")  # Priority
        assert "amatsukaze:" in message  # Tag
        assert "CRITICAL: [テスト番組] - テストエラー" in message


@pytest.mark.unit
class TestLogWriter:
    """LogWriter のテスト"""

    def test_write_both(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """Vector/Syslog両方の書き込みテスト"""
        vector_dir = tmp_path / "vector"
        syslog_dir = tmp_path / "syslog"

        writer = LogWriter(vector_log_dir=vector_dir, syslog_log_dir=syslog_dir)

        # CRITICALログ
        sample_integrated_log.labels.severity = "critical"
        sample_integrated_log.error_message = "エラー"

        vector_path, syslog_path = writer.write(sample_integrated_log)

        # 両方のファイルが作成されている
        assert vector_path is not None
        assert vector_path.exists()
        assert syslog_path is not None
        assert syslog_path.exists()

    def test_write_vector_only(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """Vector のみ書き込みテスト"""
        vector_dir = tmp_path / "vector"

        writer = LogWriter(vector_log_dir=vector_dir, syslog_log_dir=None)

        vector_path, syslog_path = writer.write(sample_integrated_log)

        # Vectorファイルのみ
        assert vector_path is not None
        assert vector_path.exists()
        assert syslog_path is None

    def test_write_non_critical(
        self, tmp_path: Path, sample_integrated_log: IntegratedLogEntry
    ) -> None:
        """CRITICAL以外の書き込みテスト"""
        vector_dir = tmp_path / "vector"
        syslog_dir = tmp_path / "syslog"

        writer = LogWriter(vector_log_dir=vector_dir, syslog_log_dir=syslog_dir)

        # severity = "info"
        vector_path, syslog_path = writer.write(sample_integrated_log)

        # Vectorファイルのみ、Syslogはスキップ
        assert vector_path is not None
        assert vector_path.exists()
        assert syslog_path is None
