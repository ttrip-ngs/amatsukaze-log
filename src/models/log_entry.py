"""ログエントリモデル

Amatsukazeログの構造化データモデル
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LogLine(BaseModel):
    """個別ログ行"""

    level: Literal["info", "warn", "error", "debug"] = Field(description="ログレベル")
    source: Literal["AMT", "FFMPEG"] = Field(description="ログソース")
    message: str = Field(description="ログメッセージ")
    timestamp_relative: str | None = Field(default=None, description="ログ内相対時刻")


class PhaseInfo(BaseModel):
    """処理フェーズ情報"""

    status: Literal["not_started", "running", "completed", "failed"] = Field(
        description="フェーズステータス"
    )
    duration: float | None = Field(default=None, description="処理時間（秒）")


class ErrorSummary(BaseModel):
    """エラーサマリ"""

    info_count: int = Field(default=0, description="infoログ数")
    warn_count: int = Field(default=0, description="warnログ数")
    error_count: int = Field(default=0, description="errorログ数")
    debug_count: int = Field(default=0, description="debugログ数")
    critical_errors: list[str] = Field(default_factory=list, description="CRITICALエラーメッセージ")


class TxtLogData(BaseModel):
    """TXTログ解析結果"""

    command_line: str = Field(description="コマンドライン引数")
    logs: list[LogLine] = Field(default_factory=list, description="ログ行リスト")
    has_critical_error: bool = Field(default=False, description="CRITICALエラー有無")
    error_summary: ErrorSummary = Field(default_factory=ErrorSummary, description="エラーサマリ")
    phases: dict[str, PhaseInfo] = Field(default_factory=dict, description="処理フェーズ情報")


class AudioDiff(BaseModel):
    """音声差分情報"""

    total_src_frames: int = Field(description="入力総フレーム数", alias="totalsrcframes")
    total_out_frames: int = Field(description="出力総フレーム数", alias="totaloutframes")
    total_out_unique_frames: int = Field(
        description="出力ユニークフレーム数", alias="totaloutuniqueframes"
    )
    not_included_per: float = Field(description="未含有率", alias="notincludedper")
    avg_diff: float = Field(description="平均差分", alias="avgdiff")
    max_diff: float = Field(description="最大差分", alias="maxdiff")
    max_diff_pos: float = Field(description="最大差分位置", alias="maxdiffpos")

    model_config = {"populate_by_name": True}


class ErrorCounts(BaseModel):
    """エラーカウント（JSON）"""

    unknown_pts: int = Field(default=0, alias="unknown-pts")
    decode_packet_failed: int = Field(default=0, alias="decode-packet-failed")
    h264_pts_mismatch: int = Field(default=0, alias="h264-pts-mismatch")
    h264_unexpected_field: int = Field(default=0, alias="h264-unexpected-field")
    non_continuous_pts: int = Field(default=0, alias="non-continuous-pts")
    no_drcs_map: int = Field(default=0, alias="no-drcs-map")
    decode_audio_failed: int = Field(default=0, alias="decode-audio-failed")

    class Config:
        populate_by_name = True


class OutFile(BaseModel):
    """出力ファイル情報"""

    path: str = Field(description="出力ファイルパス")
    srcbitrate: int = Field(description="入力ビットレート")
    outbitrate: int = Field(description="出力ビットレート")
    outfilesize: int = Field(description="出力ファイルサイズ")
    subs: list[str] = Field(default_factory=list, description="字幕ファイル")


class JsonLogData(BaseModel):
    """JSON解析結果"""

    task_id: str = Field(description="タスクID（ファイル名から生成）")
    program_name: str = Field(description="番組名")
    srcpath: str = Field(description="入力ファイルパス")
    outfiles: list[OutFile] = Field(description="出力ファイル情報")
    logofiles: list[str] = Field(default_factory=list, description="ロゴファイル")
    srcfilesize: int = Field(description="入力ファイルサイズ")
    intvideofilesize: int = Field(description="中間映像ファイルサイズ")
    outfilesize: int = Field(description="出力ファイルサイズ合計")
    srcduration: float = Field(description="入力時間（秒）")
    outduration: float = Field(description="出力時間（秒）")
    audiodiff: AudioDiff | None = Field(default=None, description="音声差分情報")
    error: ErrorCounts = Field(description="エラーカウント")
    cmanalyze: bool = Field(description="CM解析実行")
    nicojk: bool = Field(default=False, description="ニコニコ実況使用")
    trimavs: bool = Field(default=False, description="trim.avs使用")


class LokiLabels(BaseModel):
    """Lokiラベル"""

    service: str = Field(default="amatsukaze", description="サービス名")
    environment: str = Field(default="production", description="環境")
    host: str = Field(default="unknown", description="ホスト名")
    status: Literal["success", "failed", "warning"] = Field(description="ステータス")
    severity: Literal["info", "warning", "critical"] = Field(description="重要度")
    encoder: str = Field(description="エンコーダ名")


class IntegratedLogEntry(BaseModel):
    """統合ログエントリ（Vector送信用）"""

    timestamp: datetime = Field(description="タイムスタンプ")
    message: str = Field(description="サマリメッセージ")

    # Lokiラベル
    labels: LokiLabels = Field(description="Lokiラベル")

    # タスク情報
    task_id: str = Field(description="タスクID")
    program_name: str = Field(description="番組名")

    # ファイル情報
    src_path: str = Field(description="入力ファイルパス")
    out_path: str | None = Field(default=None, description="出力ファイルパス")
    src_filesize: int = Field(description="入力ファイルサイズ")
    out_filesize: int = Field(description="出力ファイルサイズ")
    compression_ratio: float = Field(description="圧縮率")

    # 時間情報
    src_duration: float = Field(description="入力時間（秒）")
    out_duration: float = Field(description="出力時間（秒）")
    duration_diff: float = Field(description="時間差分（秒）")

    # エンコーダ情報
    encoder: str = Field(description="エンコーダ名")
    format: str = Field(description="出力フォーマット")

    # エラー情報
    error_message: str | None = Field(default=None, description="エラーメッセージ")
    error_counts: dict[str, int] = Field(default_factory=dict, description="エラーカウント")

    # 処理フェーズ
    phases: dict[str, Any] = Field(default_factory=dict, description="処理フェーズ情報")

    # コマンドライン
    command_line: str = Field(description="コマンドライン引数")

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換（JSON送信用）

        Returns:
            dict: 辞書形式のログエントリ
        """
        return self.model_dump(mode="json")

    def to_syslog_message(self) -> str:
        """syslogメッセージ生成

        Returns:
            str: syslogメッセージ
        """
        severity_prefix = self.labels.severity.upper()
        status = "エンコード成功" if self.labels.status == "success" else "エンコード失敗"

        if self.error_message:
            return f"{severity_prefix}: {self.program_name} - {status}: {self.error_message}"
        else:
            return f"{severity_prefix}: {self.program_name} - {status}"
