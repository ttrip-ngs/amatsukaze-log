"""ログパーサー

AmatsukazeのTXT/JSONログを解析して構造化データに変換
"""

import json
import re
from datetime import datetime
from pathlib import Path

from src.models.log_entry import (
    AudioDiff,
    ErrorCounts,
    ErrorSummary,
    IntegratedLogEntry,
    JsonLogData,
    LogLine,
    LokiLabels,
    OutFile,
    PhaseInfo,
    TxtLogData,
)


class LogParser:
    """ログパーサークラス"""

    # ログレベルパターン
    LOG_PATTERN = re.compile(r"^(AMT|FFMPEG)\s+\[(info|warn|error|debug)\]\s+(.+)$")

    # 処理フェーズパターン
    PHASE_PATTERNS = {
        "ts_analysis": re.compile(r"TS解析完了:\s+([\d.]+)秒"),
        "logo_analysis": re.compile(r"logo scan #\d+: Finished"),
        "encode": re.compile(r"エンコード\s+\d+:\s+[\d.]+%"),
        "mux": re.compile(r"Mux完了:\s+([\d.]+)秒"),
    }

    # CRITICALエラーパターン
    CRITICAL_PATTERNS = [
        re.compile(r"Exception thrown"),
        re.compile(r"エラー.*終了します"),
        re.compile(r"failed to", re.IGNORECASE),
    ]

    def __init__(self, encoding: str = "utf-8-sig", max_log_lines: int = 10000):
        """初期化

        Args:
            encoding: ファイルエンコーディング
            max_log_lines: 最大ログ行数
        """
        self.encoding = encoding
        self.max_log_lines = max_log_lines

    def parse_txt_log(self, txt_path: Path) -> TxtLogData:
        """TXTログファイル解析

        Args:
            txt_path: TXTログファイルパス

        Returns:
            TxtLogData: 解析結果

        Raises:
            FileNotFoundError: ファイルが存在しない
            UnicodeDecodeError: エンコーディングエラー
        """
        if not txt_path.exists():
            raise FileNotFoundError(f"TXTログファイルが見つかりません: {txt_path}")

        with open(txt_path, encoding=self.encoding) as f:
            lines = f.readlines()[: self.max_log_lines]

        if not lines:
            raise ValueError("TXTログファイルが空です")

        # 1行目: コマンドライン
        command_line = lines[0].strip().lstrip("\ufeff")  # BOM除去

        # ログ行解析
        logs: list[LogLine] = []
        error_summary = ErrorSummary()
        phases: dict[str, PhaseInfo] = {
            "ts_analysis": PhaseInfo(status="not_started"),
            "logo_analysis": PhaseInfo(status="not_started"),
            "encode": PhaseInfo(status="not_started"),
            "mux": PhaseInfo(status="not_started"),
        }
        has_critical_error = False

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            # ログレベル抽出
            match = self.LOG_PATTERN.match(line)
            if match:
                source, level, message = match.groups()
                logs.append(
                    LogLine(
                        level=level,  # type: ignore
                        source=source,  # type: ignore
                        message=message,
                    )
                )

                # エラーカウント
                if level == "info":
                    error_summary.info_count += 1
                elif level == "warn":
                    error_summary.warn_count += 1
                elif level == "error":
                    error_summary.error_count += 1
                elif level == "debug":
                    error_summary.debug_count += 1

                # CRITICALエラー判定
                if any(pattern.search(message) for pattern in self.CRITICAL_PATTERNS):
                    has_critical_error = True
                    error_summary.critical_errors.append(message)

            # 処理フェーズ判定
            self._update_phases(line, phases)

        return TxtLogData(
            command_line=command_line,
            logs=logs,
            has_critical_error=has_critical_error,
            error_summary=error_summary,
            phases=phases,
        )

    def parse_json_log(self, json_path: Path) -> JsonLogData:
        """JSONログファイル解析

        Args:
            json_path: JSONログファイルパス

        Returns:
            JsonLogData: 解析結果

        Raises:
            FileNotFoundError: ファイルが存在しない
            json.JSONDecodeError: JSON解析エラー
        """
        if not json_path.exists():
            raise FileNotFoundError(f"JSONログファイルが見つかりません: {json_path}")

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        # タスクID（ファイル名から生成）
        task_id = json_path.stem  # YYYY-MM-DD_HHMMSS.mmm

        # 番組名抽出（srcpathから）
        srcpath = data["srcpath"]
        program_name = Path(srcpath).stem  # ファイル名部分

        # 出力ファイル情報
        outfiles = [OutFile(**outfile) for outfile in data.get("outfiles", [])]

        # 音声差分情報
        audiodiff = None
        if "audiodiff" in data and data["audiodiff"]:
            audiodiff = AudioDiff(**data["audiodiff"])

        # エラーカウント
        error = ErrorCounts(**data.get("error", {}))

        return JsonLogData(
            task_id=task_id,
            program_name=program_name,
            srcpath=srcpath,
            outfiles=outfiles,
            logofiles=data.get("logofiles", []),
            srcfilesize=data["srcfilesize"],
            intvideofilesize=data["intvideofilesize"],
            outfilesize=data["outfilesize"],
            srcduration=data["srcduration"],
            outduration=data["outduration"],
            audiodiff=audiodiff,
            error=error,
            cmanalyze=data["cmanalyze"],
            nicojk=data.get("nicojk", False),
            trimavs=data.get("trimavs", False),
        )

    def integrate_logs(
        self,
        txt_data: TxtLogData,
        json_data: JsonLogData,
        environment: str = "production",
        host: str = "unknown",
    ) -> IntegratedLogEntry:
        """TXTとJSONログを統合

        Args:
            txt_data: TXTログ解析結果
            json_data: JSONログ解析結果
            environment: 実行環境
            host: ホスト名

        Returns:
            IntegratedLogEntry: 統合ログエントリ
        """
        # タイムスタンプ（ファイル名から）
        timestamp = self._parse_timestamp(json_data.task_id)

        # ステータス判定
        status = self._determine_status(txt_data, json_data)

        # 重要度判定
        severity = self._determine_severity(txt_data, status)

        # エンコーダ名抽出
        encoder = self._extract_encoder(txt_data.command_line)

        # 出力フォーマット抽出
        output_format = self._extract_format(txt_data.command_line)

        # 出力パス
        out_path = json_data.outfiles[0].path if json_data.outfiles else None

        # 圧縮率計算
        compression_ratio = (
            json_data.srcfilesize / json_data.outfilesize if json_data.outfilesize > 0 else 0.0
        )

        # エラーメッセージ
        error_message = None
        if txt_data.has_critical_error and txt_data.error_summary.critical_errors:
            error_message = txt_data.error_summary.critical_errors[0]

        # サマリメッセージ生成
        message = self._generate_summary_message(json_data.program_name, status, error_message)

        # Lokiラベル
        labels = LokiLabels(
            service="amatsukaze",
            environment=environment,
            host=host,
            status=status,
            severity=severity,
            encoder=encoder,
        )

        # エラーカウント
        error_counts = {
            "info": txt_data.error_summary.info_count,
            "warn": txt_data.error_summary.warn_count,
            "error": txt_data.error_summary.error_count,
            "debug": txt_data.error_summary.debug_count,
        }

        return IntegratedLogEntry(
            timestamp=timestamp,
            message=message,
            labels=labels,
            task_id=json_data.task_id,
            program_name=json_data.program_name,
            src_path=json_data.srcpath,
            out_path=out_path,
            src_filesize=json_data.srcfilesize,
            out_filesize=json_data.outfilesize,
            compression_ratio=round(compression_ratio, 2),
            src_duration=json_data.srcduration,
            out_duration=json_data.outduration,
            duration_diff=json_data.srcduration - json_data.outduration,
            encoder=encoder,
            format=output_format,
            error_message=error_message,
            error_counts=error_counts,
            phases={k: v.model_dump() for k, v in txt_data.phases.items()},
            command_line=txt_data.command_line,
        )

    def _update_phases(self, line: str, phases: dict[str, PhaseInfo]) -> None:
        """処理フェーズ更新

        Args:
            line: ログ行
            phases: フェーズ情報辞書（更新される）
        """
        for phase_name, pattern in self.PHASE_PATTERNS.items():
            match = pattern.search(line)
            if match:
                if phase_name in ["ts_analysis", "mux"] and match.groups():
                    duration = float(match.group(1))
                    phases[phase_name] = PhaseInfo(status="completed", duration=duration)
                else:
                    phases[phase_name] = PhaseInfo(status="completed")

    def _parse_timestamp(self, task_id: str) -> datetime:
        """タスクIDからタイムスタンプ解析

        Args:
            task_id: タスクID (YYYY-MM-DD_HHMMSS.mmm)

        Returns:
            datetime: タイムスタンプ
        """
        # YYYY-MM-DD_HHMMSS.mmm → YYYY-MM-DD HH:MM:SS.mmm
        date_part, time_part = task_id.split("_")
        time_str = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
        datetime_str = f"{date_part} {time_str}"
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")

    def _determine_status(
        self, txt_data: TxtLogData, json_data: JsonLogData
    ) -> str:  # Literal["success", "failed", "warning"]
        """ステータス判定

        Args:
            txt_data: TXTログデータ
            json_data: JSONログデータ

        Returns:
            str: ステータス (success/failed/warning)
        """
        if txt_data.has_critical_error:
            return "failed"
        elif txt_data.error_summary.warn_count > 50:  # 警告多発
            return "warning"
        else:
            return "success"

    def _determine_severity(
        self, txt_data: TxtLogData, status: str
    ) -> str:  # Literal["info", "warning", "critical"]
        """重要度判定

        Args:
            txt_data: TXTログデータ
            status: ステータス

        Returns:
            str: 重要度 (info/warning/critical)
        """
        if status == "failed":
            return "critical"
        elif status == "warning":
            return "warning"
        else:
            return "info"

    def _extract_encoder(self, command_line: str) -> str:
        """エンコーダ名抽出

        Args:
            command_line: コマンドライン

        Returns:
            str: エンコーダ名
        """
        if "qsvencc" in command_line.lower():
            return "QSVEnc"
        elif "nvenc" in command_line.lower():
            return "NVEnc"
        elif "vceenc" in command_line.lower():
            return "VCEEnc"
        elif "x264" in command_line.lower():
            return "x264"
        elif "x265" in command_line.lower():
            return "x265"
        else:
            return "unknown"

    def _extract_format(self, command_line: str) -> str:
        """出力フォーマット抽出

        Args:
            command_line: コマンドライン

        Returns:
            str: 出力フォーマット
        """
        if "-fmt mkv" in command_line or ".mkv" in command_line:
            return "Matroska"
        elif "-fmt mp4" in command_line or ".mp4" in command_line:
            return "MP4"
        elif "-fmt ts" in command_line or "tsreplace" in command_line:
            return "TS"
        else:
            return "unknown"

    def _generate_summary_message(
        self, program_name: str, status: str, error_message: str | None
    ) -> str:
        """サマリメッセージ生成

        Args:
            program_name: 番組名
            status: ステータス
            error_message: エラーメッセージ

        Returns:
            str: サマリメッセージ
        """
        if status == "success":
            return f"エンコード完了: {program_name}"
        elif status == "failed":
            if error_message:
                return f"エンコード失敗: {program_name} - {error_message}"
            else:
                return f"エンコード失敗: {program_name}"
        else:
            return f"エンコード完了（警告あり）: {program_name}"
