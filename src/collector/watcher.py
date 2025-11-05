"""ログファイル監視モジュール

watchdogライブラリを使用してAmatsukazeログファイルを監視し、
新しいログファイルペア（txt + json）を検出する
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class LogFileHandler(FileSystemEventHandler):
    """ログファイルイベントハンドラ

    JSONファイルの作成を検知し、対応するTXTファイルとペアにして
    コールバック関数に渡す
    """

    def __init__(
        self,
        callback: Callable[[Path, Path], None],
        txt_wait_timeout: int = 30,
        polling_interval: float = 1.0,
    ):
        """初期化

        Args:
            callback: ファイルペア検出時のコールバック関数
            txt_wait_timeout: TXTファイル待機タイムアウト（秒）
            polling_interval: TXTファイル確認のポーリング間隔（秒）
        """
        self.callback = callback
        self.txt_wait_timeout = txt_wait_timeout
        self.polling_interval = polling_interval
        self._pending_tasks: dict[str, threading.Thread] = {}

    def on_created(self, event: FileCreatedEvent) -> None:
        """ファイル作成イベントハンドラ

        Args:
            event: ファイル作成イベント
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # JSONファイルのみ処理
        if file_path.suffix.lower() != ".json":
            return

        logger.info(f"JSONファイル検出: {file_path}")

        # 対応するTXTファイルを別スレッドで待機
        task_id = file_path.stem
        if task_id in self._pending_tasks:
            logger.warning(f"既に処理中のタスク: {task_id}")
            return

        # スレッドを作成して待機処理を開始
        thread = threading.Thread(
            target=self._wait_for_txt_file,
            args=(file_path,),
            daemon=True,
        )
        thread.start()
        self._pending_tasks[task_id] = thread

    def _wait_for_txt_file(self, json_path: Path) -> None:
        """対応するTXTファイルを待機

        Args:
            json_path: JSONファイルパス
        """
        task_id = json_path.stem
        txt_path = json_path.with_suffix(".txt")

        logger.debug(f"TXTファイル待機開始: {txt_path}")

        try:
            # タイムアウト付きでTXTファイルを待機
            elapsed = 0.0
            while elapsed < self.txt_wait_timeout:
                if txt_path.exists():
                    logger.info(f"ファイルペア検出: {json_path.name}")
                    # コールバック関数を呼び出し
                    try:
                        self.callback(txt_path, json_path)
                    except Exception as e:
                        logger.error(f"コールバック実行エラー: {e}", exc_info=True)
                    break

                time.sleep(self.polling_interval)
                elapsed += self.polling_interval
            else:
                # タイムアウト
                logger.warning(
                    f"TXTファイルタイムアウト: {txt_path} "
                    f"({self.txt_wait_timeout}秒経過)"
                )

        except Exception as e:
            logger.error(f"TXTファイル待機エラー: {e}", exc_info=True)

        finally:
            # タスクをクリーンアップ
            if task_id in self._pending_tasks:
                del self._pending_tasks[task_id]


class LogWatcher:
    """ログファイル監視クラス

    watchdog Observerを使用してディレクトリを監視し、
    新しいログファイルペアを検出する
    """

    def __init__(
        self,
        log_directory: Path,
        callback: Callable[[Path, Path], None],
        txt_wait_timeout: int = 30,
        polling_interval: float = 1.0,
    ):
        """初期化

        Args:
            log_directory: 監視するログディレクトリ
            callback: ファイルペア検出時のコールバック関数
            txt_wait_timeout: TXTファイル待機タイムアウト（秒）
            polling_interval: TXTファイル確認のポーリング間隔（秒）
        """
        self.log_directory = log_directory
        self.callback = callback
        self.txt_wait_timeout = txt_wait_timeout
        self.polling_interval = polling_interval

        # イベントハンドラとObserver
        self.event_handler = LogFileHandler(
            callback=callback,
            txt_wait_timeout=txt_wait_timeout,
            polling_interval=polling_interval,
        )
        self.observer = Observer()

        # 監視開始フラグ
        self._started = False

    def start(self) -> None:
        """監視開始"""
        if self._started:
            logger.warning("既に監視が開始されています")
            return

        # ディレクトリの存在確認
        if not self.log_directory.exists():
            raise FileNotFoundError(f"ログディレクトリが存在しません: {self.log_directory}")

        if not self.log_directory.is_dir():
            raise NotADirectoryError(f"ディレクトリではありません: {self.log_directory}")

        # Observerを開始
        self.observer.schedule(
            self.event_handler,
            str(self.log_directory),
            recursive=False,  # サブディレクトリは監視しない
        )
        self.observer.start()
        self._started = True

        logger.info(f"ログ監視開始: {self.log_directory}")

    def stop(self) -> None:
        """監視停止"""
        if not self._started:
            logger.warning("監視が開始されていません")
            return

        self.observer.stop()
        self.observer.join(timeout=5.0)
        self._started = False

        logger.info("ログ監視停止")

    def is_alive(self) -> bool:
        """監視が実行中かチェック

        Returns:
            bool: 実行中の場合True
        """
        return self._started and self.observer.is_alive()
