"""送信済みログ管理データベース

SQLiteで送信済みログを管理し、重複送信を防止
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LogDatabase:
    """送信済みログ管理クラス

    SQLiteで送信済みログを記録し、リトライ管理を行う
    """

    def __init__(self, db_path: Path):
        """初期化

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """データベース初期化"""
        # ディレクトリ作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 接続とテーブル作成
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_logs (
                task_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vector_sent BOOLEAN DEFAULT 0,
                syslog_sent BOOLEAN DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

        logger.info(f"データベース初期化完了: {self.db_path}")

    def is_processed(self, task_id: str) -> bool:
        """処理済みかチェック

        Args:
            task_id: タスクID

        Returns:
            bool: 処理済みの場合True
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT task_id FROM processed_logs WHERE task_id = ?",
            (task_id,),
        )
        return cursor.fetchone() is not None

    def mark_as_sent(
        self,
        task_id: str,
        file_path: str,
        vector_sent: bool = False,
        syslog_sent: bool = False,
    ) -> None:
        """送信済みとして記録

        Args:
            task_id: タスクID
            file_path: ログファイルパス
            vector_sent: Vector送信成功
            syslog_sent: Syslog送信成功
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        now = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO processed_logs
                (task_id, file_path, vector_sent, syslog_sent, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                vector_sent = excluded.vector_sent,
                syslog_sent = excluded.syslog_sent,
                updated_at = excluded.updated_at
            """,
            (task_id, file_path, vector_sent, syslog_sent, now),
        )
        self.conn.commit()

        logger.debug(
            f"送信記録: {task_id} (Vector: {vector_sent}, Syslog: {syslog_sent})"
        )

    def increment_retry(self, task_id: str, error_message: str) -> int:
        """リトライ回数をインクリメント

        Args:
            task_id: タスクID
            error_message: エラーメッセージ

        Returns:
            int: 新しいリトライ回数
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        now = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE processed_logs
            SET retry_count = retry_count + 1,
                last_error = ?,
                updated_at = ?
            WHERE task_id = ?
            """,
            (error_message, now, task_id),
        )
        self.conn.commit()

        # 新しいリトライ回数を取得
        cursor.execute(
            "SELECT retry_count FROM processed_logs WHERE task_id = ?",
            (task_id,),
        )
        row = cursor.fetchone()
        retry_count = row["retry_count"] if row else 0

        logger.debug(f"リトライ記録: {task_id} (count: {retry_count})")
        return retry_count

    def get_retry_count(self, task_id: str) -> int:
        """リトライ回数を取得

        Args:
            task_id: タスクID

        Returns:
            int: リトライ回数（未記録の場合0）
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT retry_count FROM processed_logs WHERE task_id = ?",
            (task_id,),
        )
        row = cursor.fetchone()
        return row["retry_count"] if row else 0

    def get_failed_logs(self, max_retry: int = 5) -> list[dict]:
        """送信失敗ログを取得

        Args:
            max_retry: 最大リトライ回数

        Returns:
            list[dict]: 失敗ログリスト
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT task_id, file_path, retry_count, last_error,
                   vector_sent, syslog_sent
            FROM processed_logs
            WHERE (vector_sent = 0 OR syslog_sent = 0)
              AND retry_count < ?
            ORDER BY updated_at ASC
            """,
            (max_retry,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_records(self, days: int = 30) -> int:
        """古いレコードを削除

        Args:
            days: 保持日数

        Returns:
            int: 削除件数
        """
        if not self.conn:
            raise RuntimeError("データベース未初期化")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            DELETE FROM processed_logs
            WHERE processed_at < datetime('now', '-' || ? || ' days')
            """,
            (days,),
        )
        deleted = cursor.rowcount
        self.conn.commit()

        logger.info(f"古いレコード削除: {deleted}件")
        return deleted

    def close(self) -> None:
        """データベース接続をクローズ"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("データベース接続をクローズ")

    def __enter__(self) -> "LogDatabase":
        """コンテキストマネージャー開始"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """コンテキストマネージャー終了"""
        self.close()
