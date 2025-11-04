"""ログパーサーのテスト"""

from pathlib import Path

import pytest

from src.collector.parser import LogParser


class TestLogParser:
    """LogParserクラスのテスト"""

    @pytest.fixture
    def parser(self) -> LogParser:
        """パーサーインスタンス"""
        return LogParser()

    @pytest.fixture
    def sample_log_dir(self) -> Path:
        """サンプルログディレクトリ"""
        return Path("tmp/sample_log")

    def test_parse_txt_log_success(self, parser: LogParser, sample_log_dir: Path) -> None:
        """TXTログ解析成功ケース"""
        txt_path = sample_log_dir / "2025-10-19_131358.440.txt"

        if not txt_path.exists():
            pytest.skip(f"サンプルログが存在しません: {txt_path}")

        result = parser.parse_txt_log(txt_path)

        assert result.command_line.startswith("/app/exe_files/AmatsukazeCLI")
        assert len(result.logs) > 0
        assert result.error_summary.info_count > 0

    def test_parse_txt_log_with_error(self, parser: LogParser, sample_log_dir: Path) -> None:
        """TXTログ解析エラーケース"""
        txt_path = sample_log_dir / "2025-10-18_015420.932.txt"

        if not txt_path.exists():
            pytest.skip(f"サンプルログが存在しません: {txt_path}")

        result = parser.parse_txt_log(txt_path)

        assert result.has_critical_error is True
        assert result.error_summary.error_count > 0
        assert len(result.error_summary.critical_errors) > 0
        assert "Exception thrown" in result.error_summary.critical_errors[0]

    def test_parse_txt_log_file_not_found(self, parser: LogParser) -> None:
        """TXTログファイルが存在しない"""
        with pytest.raises(FileNotFoundError):
            parser.parse_txt_log(Path("nonexistent.txt"))

    def test_parse_json_log_success(self, parser: LogParser, sample_log_dir: Path) -> None:
        """JSONログ解析成功ケース"""
        json_path = sample_log_dir / "2025-10-19_131358.440.json"

        if not json_path.exists():
            pytest.skip(f"サンプルログが存在しません: {json_path}")

        result = parser.parse_json_log(json_path)

        assert result.task_id == "2025-10-19_131358.440"
        assert result.program_name != ""
        assert result.srcfilesize > 0
        assert result.outfilesize > 0
        assert result.srcduration > 0
        assert result.outduration > 0

    def test_parse_json_log_file_not_found(self, parser: LogParser) -> None:
        """JSONログファイルが存在しない"""
        with pytest.raises(FileNotFoundError):
            parser.parse_json_log(Path("nonexistent.json"))

    def test_integrate_logs_success(self, parser: LogParser, sample_log_dir: Path) -> None:
        """ログ統合成功ケース"""
        txt_path = sample_log_dir / "2025-10-19_131358.440.txt"
        json_path = sample_log_dir / "2025-10-19_131358.440.json"

        if not txt_path.exists() or not json_path.exists():
            pytest.skip("サンプルログが存在しません")

        txt_data = parser.parse_txt_log(txt_path)
        json_data = parser.parse_json_log(json_path)
        result = parser.integrate_logs(txt_data, json_data)

        assert result.task_id == "2025-10-19_131358.440"
        assert result.labels.service == "amatsukaze"
        assert result.labels.status in ["success", "failed", "warning"]
        assert result.labels.severity in ["info", "warning", "critical"]
        assert result.compression_ratio > 0
        assert result.message != ""

    def test_integrate_logs_failed(self, parser: LogParser, sample_log_dir: Path) -> None:
        """ログ統合失敗ケース"""
        txt_path = sample_log_dir / "2025-10-18_015420.932.txt"
        json_path = sample_log_dir / "2025-10-18_020404.624.json"

        if not txt_path.exists() or not json_path.exists():
            pytest.skip("サンプルログが存在しません")

        txt_data = parser.parse_txt_log(txt_path)
        json_data = parser.parse_json_log(json_path)
        result = parser.integrate_logs(txt_data, json_data)

        assert result.labels.status == "failed"
        assert result.labels.severity == "critical"
        assert result.error_message is not None
        assert "DRCS" in result.error_message or "Exception" in result.error_message

    def test_extract_encoder(self, parser: LogParser) -> None:
        """エンコーダ名抽出テスト"""
        assert parser._extract_encoder("-e qsvencc") == "QSVEnc"
        assert parser._extract_encoder("-e nvenc") == "NVEnc"
        assert parser._extract_encoder("-e x264") == "x264"
        assert parser._extract_encoder("-e unknown") == "unknown"

    def test_extract_format(self, parser: LogParser) -> None:
        """出力フォーマット抽出テスト"""
        assert parser._extract_format("-fmt mkv -o output.mkv") == "Matroska"
        assert parser._extract_format("-fmt mp4 -o output.mp4") == "MP4"
        assert parser._extract_format("-fmt ts -m tsreplace") == "TS"
        assert parser._extract_format("-o output.avi") == "unknown"

    def test_parse_timestamp(self, parser: LogParser) -> None:
        """タイムスタンプ解析テスト"""
        timestamp = parser._parse_timestamp("2025-10-19_131358.440")
        assert timestamp.year == 2025
        assert timestamp.month == 10
        assert timestamp.day == 19
        assert timestamp.hour == 13
        assert timestamp.minute == 13
        assert timestamp.second == 58
        assert timestamp.microsecond == 440000

    def test_determine_status(self, parser: LogParser) -> None:
        """ステータス判定テスト"""
        from src.models.log_entry import ErrorSummary, JsonLogData, TxtLogData

        # 成功ケース
        txt_data_success = TxtLogData(
            command_line="test",
            has_critical_error=False,
            error_summary=ErrorSummary(warn_count=10),
        )
        json_data = JsonLogData(
            task_id="test",
            program_name="test",
            srcpath="test",
            outfiles=[],
            srcfilesize=100,
            intvideofilesize=90,
            outfilesize=80,
            srcduration=100.0,
            outduration=90.0,
            error={"unknown-pts": 0},
            cmanalyze=True,
        )
        assert parser._determine_status(txt_data_success, json_data) == "success"

        # 失敗ケース
        txt_data_failed = TxtLogData(
            command_line="test",
            has_critical_error=True,
            error_summary=ErrorSummary(error_count=1, critical_errors=["Error"]),
        )
        assert parser._determine_status(txt_data_failed, json_data) == "failed"

        # 警告ケース
        txt_data_warning = TxtLogData(
            command_line="test",
            has_critical_error=False,
            error_summary=ErrorSummary(warn_count=100),
        )
        assert parser._determine_status(txt_data_warning, json_data) == "warning"
