"""送信済みログ管理データベース

ファイル書き込み済みログを管理し、重複処理を防止
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class LogDatabase:
    """ログ処理管理データベース

    SQLiteで処理済みログを管理し、重複処理を防止
    """

    def __init__(self, db_path: Path):
        """初期化

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """データベース初期化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_logs (
                task_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vector_file TEXT,
                syslog_file TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        logger.info(f"データベース初期化完了: {self.db_path}")

    def is_processed(self, task_id: str) -> bool:
        """タスクが処理済みかチェック

        Args:
            task_id: タスクID

        Returns:
            bool: 処理済みの場合True
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute("SELECT task_id FROM processed_logs WHERE task_id = ?", (task_id,))
        return cursor.fetchone() is not None

    def mark_as_processed(
        self,
        task_id: str,
        file_path: str,
        vector_file: str | None = None,
        syslog_file: str | None = None,
    ) -> None:
        """処理済みとして記録

        Args:
            task_id: タスクID
            file_path: 元ファイルパス
            vector_file: Vector用ファイルパス
            syslog_file: Syslog用ファイルパス
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO processed_logs
                (task_id, file_path, vector_file, syslog_file, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                vector_file = excluded.vector_file,
                syslog_file = excluded.syslog_file,
                updated_at = excluded.updated_at
            """,
            (task_id, file_path, vector_file, syslog_file, datetime.now().isoformat()),
        )
        self.conn.commit()
        logger.debug(f"処理済み記録: {task_id}")

    def cleanup_old_records(self, days: int = 30) -> int:
        """古いレコードを削除

        Args:
            days: 保持日数

        Returns:
            int: 削除件数
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM processed_logs WHERE processed_at < ?", (cutoff_date,)
        )
        deleted = cursor.rowcount
        self.conn.commit()

        logger.info(f"古いレコード削除: {deleted}件 (保持期間: {days}日)")
        return deleted

    def close(self) -> None:
        """データベース接続をクローズ"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("データベース接続クローズ")

    def __enter__(self):
        """コンテキストマネージャー: enter"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー: exit"""
        self.close()
