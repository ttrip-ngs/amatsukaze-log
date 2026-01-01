"""メインアプリケーション

Amatsukazeログ収集・変換・書き込みを統合実行
"""

import logging
import signal
import sys
from pathlib import Path
from typing import NoReturn

from src.collector.database import LogDatabase
from src.collector.parser import LogParser
from src.collector.watcher import LogWatcher
from src.collector.writer import LogFileWriter, LogWriter, SyslogFileWriter
from src.models.config import Config

logger = logging.getLogger(__name__)


class LogCollectorApp:
    """ログ収集アプリケーション

    Amatsukazeのログファイルを監視し、パース・変換・ファイル出力を実行
    """

    def __init__(self, config: Config):
        """初期化

        Args:
            config: アプリケーション設定
        """
        self.config = config
        self.running = False

        # コンポーネント初期化
        self.database = LogDatabase(config.writer.database.path)
        self.parser = LogParser(
            encoding=config.parser.encoding,
            max_log_lines=config.parser.max_log_lines,
            critical_rules=config.parser.critical_rules,
        )

        # ライター初期化
        vector_log_dir = config.writer.vector.log_directory if config.writer.vector.enabled else None
        syslog_log_dir = config.writer.syslog.log_directory if config.writer.syslog.enabled else None

        self.writer = LogWriter(
            vector_log_dir=vector_log_dir,
            syslog_log_dir=syslog_log_dir,
            rotate_size=config.writer.vector.rotate_size,
        )

        # ウォッチャー初期化
        self.watcher = LogWatcher(
            log_directory=config.watcher.log_directory,
            callback=self._process_log_files,
            txt_wait_timeout=config.watcher.txt_wait_timeout,
            polling_interval=config.watcher.polling_interval,
        )

        # シグナルハンドラ登録
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info("ログ収集アプリケーション初期化完了")

    def _process_log_files(self, txt_path: Path, json_path: Path) -> None:
        """ログファイルペア処理

        Args:
            txt_path: TXTログファイルパス
            json_path: JSONログファイルパス
        """
        try:
            # タスクIDを取得
            task_id = json_path.stem

            # 重複チェック
            if self.database.is_processed(task_id):
                logger.info(f"既に処理済み: {task_id}")
                return

            logger.info(f"ログファイル処理開始: {task_id}")

            # ログパース
            integrated_log = self.parser.parse(txt_path, json_path)

            # ファイル書き込み
            vector_file, syslog_file = self.writer.write(integrated_log)

            # 処理済み記録
            self.database.mark_as_processed(
                task_id=task_id,
                file_path=str(json_path),
                vector_file=str(vector_file) if vector_file else None,
                syslog_file=str(syslog_file) if syslog_file else None,
            )

            logger.info(
                f"ログファイル処理完了: {task_id} "
                f"(vector={vector_file is not None}, syslog={syslog_file is not None})"
            )

        except Exception as e:
            logger.error(f"ログファイル処理エラー: {txt_path}, {json_path} - {e}", exc_info=True)

    def _signal_handler(self, signum: int, frame) -> None:
        """シグナルハンドラ

        Args:
            signum: シグナル番号
            frame: フレーム
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"シグナル受信: {signal_name}")
        self.stop()

    def start(self) -> None:
        """アプリケーション開始"""
        logger.info("ログ収集アプリケーション開始")

        try:
            # パスのバリデーション
            self.config.validate_paths()

            # ウォッチャー開始
            self.watcher.start()
            self.running = True

            logger.info(
                f"ログ監視中: {self.config.watcher.log_directory} "
                f"(Vector={self.config.writer.vector.enabled}, "
                f"Syslog={self.config.writer.syslog.enabled})"
            )

            # メインループ（Ctrl+Cまで待機）
            while self.running:
                signal.pause()

        except KeyboardInterrupt:
            logger.info("キーボード割り込み検知")
            self.stop()
        except Exception as e:
            logger.error(f"アプリケーションエラー: {e}", exc_info=True)
            self.stop()
            sys.exit(1)

    def stop(self) -> None:
        """アプリケーション停止"""
        if not self.running:
            return

        logger.info("ログ収集アプリケーション停止中...")
        self.running = False

        # ウォッチャー停止
        try:
            self.watcher.stop()
        except Exception as e:
            logger.warning(f"ウォッチャー停止エラー: {e}")

        # データベースクローズ
        try:
            self.database.close()
        except Exception as e:
            logger.warning(f"データベースクローズエラー: {e}")

        logger.info("ログ収集アプリケーション停止完了")


def setup_logging(config: Config) -> None:
    """ロギング設定

    Args:
        config: アプリケーション設定
    """
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)

    if config.logging.format == "json":
        # JSON形式（構造化ログ）
        import json
        from datetime import UTC, datetime

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data, ensure_ascii=False)

        formatter = JsonFormatter()
    else:
        # テキスト形式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # ハンドラ設定
    if config.logging.output == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


def main() -> NoReturn:
    """メインエントリーポイント"""
    # 設定ファイルパス
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print(f"設定ファイルが見つかりません: {config_path}", file=sys.stderr)
        sys.exit(1)

    # 設定読み込み
    try:
        config = Config.from_yaml(config_path)
    except Exception as e:
        print(f"設定ファイル読み込みエラー: {e}", file=sys.stderr)
        sys.exit(1)

    # ロギング設定
    setup_logging(config)

    # アプリケーション開始
    app = LogCollectorApp(config)
    app.start()

    sys.exit(0)


if __name__ == "__main__":
    main()
