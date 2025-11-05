"""ログファイル監視機能のユニットテスト"""

import asyncio
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.collector.watcher import LogWatcher


@pytest.fixture
def temp_log_dir(tmp_path: Path) -> Path:
    """一時ログディレクトリを作成

    Args:
        tmp_path: pytestの一時ディレクトリ

    Returns:
        Path: ログディレクトリパス
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def callback_mock() -> Mock:
    """コールバック関数のモックを作成

    Returns:
        Mock: モックオブジェクト
    """
    return Mock()


@pytest.mark.unit
def test_watcher_initialization(temp_log_dir: Path, callback_mock: Mock) -> None:
    """ログ監視の初期化テスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
        txt_wait_timeout=10,
        polling_interval=0.5,
    )

    assert watcher.log_directory == temp_log_dir
    assert watcher.callback == callback_mock
    assert watcher.txt_wait_timeout == 10
    assert watcher.polling_interval == 0.5
    assert not watcher.is_alive()


@pytest.mark.unit
def test_watcher_start_stop(temp_log_dir: Path, callback_mock: Mock) -> None:
    """ログ監視の開始・停止テスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
    )

    # 開始
    watcher.start()
    assert watcher.is_alive()

    # 停止
    watcher.stop()
    assert not watcher.is_alive()


@pytest.mark.unit
def test_watcher_invalid_directory(callback_mock: Mock) -> None:
    """存在しないディレクトリ指定時のエラーテスト

    Args:
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=Path("/nonexistent/directory"),
        callback=callback_mock,
    )

    with pytest.raises(FileNotFoundError):
        watcher.start()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_watcher_file_detection(temp_log_dir: Path, callback_mock: Mock) -> None:
    """ファイルペア検出テスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
        txt_wait_timeout=5,
        polling_interval=0.1,
    )

    watcher.start()

    try:
        # TXTファイルを先に作成
        txt_file = temp_log_dir / "2025-10-18_120000.000.txt"
        txt_file.write_text("test log content")

        # 少し待機
        await asyncio.sleep(0.2)

        # JSONファイルを作成（トリガー）
        json_file = temp_log_dir / "2025-10-18_120000.000.json"
        json_file.write_text('{"test": "data"}')

        # コールバックが呼ばれるまで待機
        await asyncio.sleep(1.0)

        # コールバックが呼ばれたことを確認
        callback_mock.assert_called_once()
        args = callback_mock.call_args[0]
        assert args[0] == txt_file  # TXTファイルパス
        assert args[1] == json_file  # JSONファイルパス

    finally:
        watcher.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_watcher_txt_delayed(temp_log_dir: Path, callback_mock: Mock) -> None:
    """TXTファイル遅延作成テスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
        txt_wait_timeout=5,
        polling_interval=0.1,
    )

    watcher.start()

    try:
        # JSONファイルを先に作成
        json_file = temp_log_dir / "2025-10-18_120001.000.json"
        json_file.write_text('{"test": "data"}')

        # 少し待機してからTXTファイルを作成
        await asyncio.sleep(0.5)
        txt_file = temp_log_dir / "2025-10-18_120001.000.txt"
        txt_file.write_text("test log content")

        # コールバックが呼ばれるまで待機
        await asyncio.sleep(1.0)

        # コールバックが呼ばれたことを確認
        callback_mock.assert_called_once()
        args = callback_mock.call_args[0]
        assert args[0] == txt_file
        assert args[1] == json_file

    finally:
        watcher.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_watcher_txt_timeout(temp_log_dir: Path, callback_mock: Mock) -> None:
    """TXTファイルタイムアウトテスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
        txt_wait_timeout=1,  # 短いタイムアウト
        polling_interval=0.1,
    )

    watcher.start()

    try:
        # JSONファイルのみ作成（TXTファイルなし）
        json_file = temp_log_dir / "2025-10-18_120002.000.json"
        json_file.write_text('{"test": "data"}')

        # タイムアウトより長く待機
        await asyncio.sleep(2.0)

        # コールバックが呼ばれていないことを確認
        callback_mock.assert_not_called()

    finally:
        watcher.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_watcher_ignore_non_json(temp_log_dir: Path, callback_mock: Mock) -> None:
    """JSON以外のファイルを無視するテスト

    Args:
        temp_log_dir: 一時ログディレクトリ
        callback_mock: コールバックモック
    """
    watcher = LogWatcher(
        log_directory=temp_log_dir,
        callback=callback_mock,
    )

    watcher.start()

    try:
        # TXTファイルのみ作成
        txt_file = temp_log_dir / "2025-10-18_120003.000.txt"
        txt_file.write_text("test log content")

        # 少し待機
        await asyncio.sleep(1.0)

        # コールバックが呼ばれていないことを確認
        callback_mock.assert_not_called()

    finally:
        watcher.stop()
