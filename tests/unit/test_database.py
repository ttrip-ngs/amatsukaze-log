"""送信済みログ管理データベースのユニットテスト"""

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

    def test_mark_as_processed(self, temp_db: Path) -> None:
        """処理済み記録テスト"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"
            vector_file = "/var/log/vector/amatsukaze-20251018.jsonl"
            syslog_file = "/var/log/syslog/amatsukaze-critical-20251018.log"

            # 処理済み記録
            db.mark_as_processed(
                task_id=task_id,
                file_path=file_path,
                vector_file=vector_file,
                syslog_file=syslog_file,
            )

            # 記録確認
            assert db.is_processed(task_id) is True

            # データ内容確認
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT file_path, vector_file, syslog_file FROM processed_logs WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["file_path"] == file_path
            assert row["vector_file"] == vector_file
            assert row["syslog_file"] == syslog_file

    def test_mark_as_processed_update(self, temp_db: Path) -> None:
        """処理済み更新テスト（ON CONFLICT UPDATE）"""
        with LogDatabase(temp_db) as db:
            task_id = "2025-10-18_120000.000"
            file_path = "/test/path/2025-10-18_120000.000.json"

            # 1回目: Vectorのみ
            db.mark_as_processed(
                task_id=task_id,
                file_path=file_path,
                vector_file="/var/log/vector/file1.jsonl",
                syslog_file=None,
            )

            # 2回目: Syslogも追加
            db.mark_as_processed(
                task_id=task_id,
                file_path=file_path,
                vector_file="/var/log/vector/file1.jsonl",
                syslog_file="/var/log/syslog/file1.log",
            )

            # データ内容確認
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT vector_file, syslog_file FROM processed_logs WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["vector_file"] == "/var/log/vector/file1.jsonl"
            assert row["syslog_file"] == "/var/log/syslog/file1.log"

    def test_cleanup_old_records(self, temp_db: Path) -> None:
        """古いレコード削除テスト"""
        with LogDatabase(temp_db) as db:
            # 古いレコード（31日前）
            old_task_id = "old_task"
            db.mark_as_processed(
                task_id=old_task_id,
                file_path="/test/old.json",
                vector_file="/var/log/vector/old.jsonl",
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
            db.mark_as_processed(
                task_id=new_task_id,
                file_path="/test/new.json",
                vector_file="/var/log/vector/new.jsonl",
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
            db.mark_as_processed(
                task_id="test_task",
                file_path="/test/test.json",
                vector_file="/var/log/vector/test.jsonl",
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

    def test_db_error_handling(self, temp_db: Path) -> None:
        """データベースエラーハンドリングテスト"""
        db = LogDatabase(temp_db)

        # 接続をクローズ
        db.close()

        # クローズ後の操作はエラー
        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.is_processed("test")

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.mark_as_processed("test", "/test", "/var/log/vector/test.jsonl")

        with pytest.raises(RuntimeError, match="データベース未初期化"):
            db.cleanup_old_records()
