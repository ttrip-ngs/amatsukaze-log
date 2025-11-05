"""送信済みログ管理データベースのユニットテスト"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.collector.database import LogDatabase


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """テスト用の一時DBパス"""
    return tmp_path / "test_logs.db"


@pytest.mark.unit
class TestLogDatabase:
    """LogDatabase のテスト"""

    def test_initialize_db(self, temp_db: Path) -> None:
        """データベース初期化テスト"""
        db = LogDatabase(temp_db)

        # DBファイルが作成されている
        assert temp_db.exists()

        # テーブルが作成されている
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_logs'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "processed_logs"

        db.close()

    def test_is_processed_new_task(self, temp_db: Path) -> None:
        """未処理タスクのチェックテスト"""
        with LogDatabase(temp_db) as db:
            result = db.is_processed("2025-10-18_120000.000")
            assert result is False

    def test_mark_as_sent(self, temp_db: Path) -> None:
        """送信済み記録テスト"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 送信記録
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=True,
                syslog_sent=False,
            )

            # 記録確認
            assert db.is_processed(task_id) is True

            # データ内容確認
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT file_path, vector_sent, syslog_sent FROM processed_logs WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["file_path"] == file_path
            assert row["vector_sent"] == 1
            assert row["syslog_sent"] == 0

    def test_mark_as_sent_update(self, temp_db: Path) -> None:
        """送信済み更新テスト（ON CONFLICT UPDATE）"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 1回目: Vector送信のみ
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=True,
                syslog_sent=False,
            )

            # 2回目: Syslog送信も成功
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=True,
                syslog_sent=True,
            )

            # データ内容確認
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT vector_sent, syslog_sent FROM processed_logs WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["vector_sent"] == 1
            assert row["syslog_sent"] == 1

    def test_increment_retry(self, temp_db: Path) -> None:
        """リトライ回数インクリメントテスト"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 初回記録
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=False,
                syslog_sent=False,
            )

            # リトライ1回目
            retry_count = db.increment_retry(task_id, "Connection timeout")
            assert retry_count == 1

            # リトライ2回目
            retry_count = db.increment_retry(task_id, "Connection refused")
            assert retry_count == 2

            # エラーメッセージ確認
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT retry_count, last_error FROM processed_logs WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["retry_count"] == 2
            assert row["last_error"] == "Connection refused"

    def test_get_retry_count(self, temp_db: Path) -> None:
        """リトライ回数取得テスト"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 未記録の場合
            assert db.get_retry_count(task_id) == 0

            # 記録後
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=False,
                syslog_sent=False,
            )
            assert db.get_retry_count(task_id) == 0

            # リトライ後
            db.increment_retry(task_id, "Error")
            assert db.get_retry_count(task_id) == 1

    def test_get_failed_logs(self, temp_db: Path) -> None:
        """失敗ログ取得テスト"""
        with LogDatabase(temp_db) as db:
            # 成功ケース（取得対象外）
            db.mark_as_sent(
                task_id="success_1",
                file_path="/test/success_1.json",
                vector_sent=True,
                syslog_sent=True,
            )

            # 失敗ケース1: Vector失敗
            db.mark_as_sent(
                task_id="failed_1",
                file_path="/test/failed_1.json",
                vector_sent=False,
                syslog_sent=True,
            )
            db.increment_retry("failed_1", "Vector error")

            # 失敗ケース2: Syslog失敗
            db.mark_as_sent(
                task_id="failed_2",
                file_path="/test/failed_2.json",
                vector_sent=True,
                syslog_sent=False,
            )
            db.increment_retry("failed_2", "Syslog error")

            # リトライ上限超過ケース（取得対象外）
            db.mark_as_sent(
                task_id="retry_exceeded",
                file_path="/test/retry_exceeded.json",
                vector_sent=False,
                syslog_sent=False,
            )
            for _ in range(6):
                db.increment_retry("retry_exceeded", "Max retry exceeded")

            # 失敗ログ取得（max_retry=5）
            failed_logs = db.get_failed_logs(max_retry=5)

            # 2件取得される
            assert len(failed_logs) == 2

            task_ids = {log["task_id"] for log in failed_logs}
            assert "failed_1" in task_ids
            assert "failed_2" in task_ids
            assert "success_1" not in task_ids
            assert "retry_exceeded" not in task_ids

    def test_cleanup_old_records(self, temp_db: Path) -> None:
        """古いレコード削除テスト"""
        with LogDatabase(temp_db) as db:
            # 古いレコード（31日前）
            old_task_id = "old_task"
            db.mark_as_sent(
                task_id=old_task_id,
                file_path="/test/old.json",
                vector_sent=True,
                syslog_sent=True,
            )

            # processed_atを手動で古い日付に変更
            cursor = db.conn.cursor()
            old_date = (datetime.now() - timedelta(days=31)).isoformat()
            cursor.execute(
                "UPDATE processed_logs SET processed_at = ? WHERE task_id = ?",
                (old_date, old_task_id),
            )
            db.conn.commit()

            # 新しいレコード（今日）
            new_task_id = "new_task"
            db.mark_as_sent(
                task_id=new_task_id,
                file_path="/test/new.json",
                vector_sent=True,
                syslog_sent=True,
            )

            # クリーンアップ実行（30日保持）
            deleted = db.cleanup_old_records(days=30)

            # 1件削除
            assert deleted == 1

            # 古いレコードは削除されている
            assert db.is_processed(old_task_id) is False

            # 新しいレコードは残っている
            assert db.is_processed(new_task_id) is True

    def test_context_manager(self, temp_db: Path) -> None:
        """コンテキストマネージャーテスト"""
        # withブロック内でDB操作
        with LogDatabase(temp_db) as db:
            db.mark_as_sent(
                task_id="test_task",
                file_path="/test/test.json",
                vector_sent=True,
                syslog_sent=True,
            )
            assert db.conn is not None

        # withブロック外では接続がクローズされている
        assert db.conn is None

    def test_close(self, temp_db: Path) -> None:
        """クローズテスト"""
        db = LogDatabase(temp_db)
        assert db.conn is not None

        db.close()
        assert db.conn is None

        # 2回クローズしてもエラーにならない
        db.close()

    def test_multiple_operations(self, temp_db: Path) -> None:
        """複数操作の統合テスト"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 1. 未処理確認
            assert db.is_processed(task_id) is False

            # 2. 送信記録（Vector失敗）
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=False,
                syslog_sent=True,
            )
            assert db.is_processed(task_id) is True
            assert db.get_retry_count(task_id) == 0

            # 3. リトライ
            db.increment_retry(task_id, "Vector timeout")
            assert db.get_retry_count(task_id) == 1

            # 4. 失敗ログ取得
            failed_logs = db.get_failed_logs()
            assert len(failed_logs) == 1
            assert failed_logs[0]["task_id"] == task_id

            # 5. リトライ成功、送信記録更新
            db.mark_as_sent(
                task_id=task_id,
                file_path=file_path,
                vector_sent=True,
                syslog_sent=True,
            )

            # 6. 失敗ログから除外
            failed_logs = db.get_failed_logs()
            assert len(failed_logs) == 0

    def test_db_error_handling(self, temp_db: Path) -> None:
        """データベースエラーハンドリングテスト"""
        db = LogDatabase(temp_db)

        # 接続をクローズ
        db.close()

        # クローズ後の操作はエラー
        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.is_processed("test")

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.mark_as_sent("test", "/test", True, True)

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.increment_retry("test", "error")

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.get_retry_count("test")

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.get_failed_logs()

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.cleanup_old_records()
